"""
Regras de negócio das ações (antes: Server Actions + RLS).

Cada função valida, grava e dispara os efeitos (e-mail, notificação). Erros
de negócio voltam como `Resultado(erro=...)`, nunca como exceção — as views
só traduzem o resultado em resposta HTTP. Isso também deixa as regras prontas
para uma futura API (ver docs/05-roadmap-api.md do projeto original).
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.html import escape

from contas.models import Papel

from . import emails
from .labels import (
    CATEGORIAS_COM_PRODUTOS,
    CATEGORIAS_COM_REFERENCIA,
    CATEGORIAS_COM_SINAL_VOLUME,
    CATEGORIAS_DISPENSAM_DADOS_PRODUTO,
    CATEGORIAS_EXIGEM_FOTO,
    ITEM_CATEGORIA_LABEL,
    ITEM_CATEGORIAS,
    STATUS_BLOQUEADOS,
    STATUS_LABEL,
    TIPOS_FORM,
    REFERENCIA_FORM,
    EventoTipo,
    Prioridade,
    ReferenciaTipo,
    SinalVolume,
    Status,
    formatar_referencia,
)
from .models import Anexo, ContatoEncaminhamento, EventoOcorrencia, Mensagem, Ocorrencia, OcorrenciaItem
from .permissoes import colegas_da_empresa, ocorrencias_visiveis
from .uploads import validar_arquivos

log = logging.getLogger("ocorrencias")

MAX_ITENS = 100


@dataclass
class Resultado:
    erro: str | None = None
    aviso: str | None = None
    dados: dict = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.erro is None


def _salvar_anexos(oc, arquivos, autor, mensagem=None) -> list[str]:
    """Grava os anexos e devolve os nomes que falharam."""
    falhas = []
    for a in arquivos:
        try:
            Anexo.objects.create(
                ocorrencia=oc,
                mensagem=mensagem,
                arquivo=a,
                nome_arquivo=a.name,
                tipo_mime=a.content_type,
                tamanho_bytes=a.size,
                enviado_por=autor,
            )
        except Exception as e:  # noqa: BLE001
            log.warning("[anexo] falha ao salvar %s: %s", a.name, e)
            falhas.append(a.name)
    return falhas


# ---------------------------------------------------------------- portal


def verificar_duplicata(user, referencia: str) -> dict | None:
    """
    A empresa já tem ocorrência em andamento com a mesma referência (NF, Pedido ou Picking)? Avisa o
    cliente antes de abrir outra (não bloqueia).
    """
    ref = (referencia or "").strip()
    if not ref:
        return None
    oc = (
        ocorrencias_visiveis(user)
        .filter(referencia=ref, excluida_em__isnull=True, status__in=["aberta", "em_analise", "resolvida"])
        .order_by("-criado_em")
        .first()
    )
    if not oc:
        return None
    if oc.cliente_id == user.pk:
        return {"protocolo": oc.protocolo, "abertaPor": None}
    nome = colegas_da_empresa(user).get(oc.cliente_id, "um colega da empresa")
    return {"protocolo": oc.protocolo, "abertaPor": nome}


def _preparar_itens(itens_json: str) -> tuple[list[dict], str | None]:
    try:
        brutos = json.loads(itens_json or "[]")
        if not isinstance(brutos, list):
            brutos = []
    except (json.JSONDecodeError, TypeError):
        brutos = []
    if len(brutos) > MAX_ITENS:
        return [], f"Máximo de {MAX_ITENS} produtos por ocorrência. Reduza a lista."

    preparados = []
    for it in brutos:
        if not isinstance(it, dict):
            continue
        categoria = str(it.get("categoria") or "")
        if categoria not in ITEM_CATEGORIAS:
            continue
        codigo = str(it.get("codigo") or "").strip()
        descricao = str(it.get("descricao") or "").strip()
        try:
            quantidade = int(it.get("quantidade"))
        except (TypeError, ValueError):
            quantidade = 0

        # "Troca de volume": o cliente não abriu o produto, então código,
        # descrição e quantidade detalhados são dispensados (a foto é exigida à parte).
        dispensa = categoria in CATEGORIAS_DISPENSAM_DADOS_PRODUTO
        if dispensa:
            descricao = descricao or ITEM_CATEGORIA_LABEL[categoria]
            if quantidade <= 0:
                quantidade = 1

        # Troca de volume: o cliente diz se o volume falta ou sobra (spec 004).
        # Recusa explícita, para não descartar o item em silêncio.
        sinal_volume = None
        if categoria in CATEGORIAS_COM_SINAL_VOLUME:
            sinal_volume = str(it.get("sinal_volume") or "")
            if sinal_volume not in SinalVolume.values:
                return [], "Na troca de volume, informe se o volume está faltando ou sobrando."

        if (dispensa or codigo) and descricao and quantidade > 0:
            preparados.append(
                {
                    "categoria": categoria,
                    "codigo": codigo,
                    "descricao": descricao,
                    "quantidade": quantidade,
                    "sinal_volume": sinal_volume,
                }
            )
    return preparados, None


def criar_ocorrencia(user, dados, arquivos) -> Resultado:
    if not user.eh_cliente:
        return Resultado("Apenas clientes podem abrir ocorrências.")

    tipo = dados.get("tipo", "")
    descricao = (dados.get("descricao") or "").strip()
    referencia = (dados.get("referencia") or "").strip()
    referencia_tipo = dados.get("referencia_tipo") or ""

    if tipo not in TIPOS_FORM:
        return Resultado("Selecione um tipo válido.")

    eh_produtos = tipo in CATEGORIAS_COM_PRODUTOS

    # Descrição: obrigatória, exceto em "Produtos" (os itens já descrevem).
    if not eh_produtos and len(descricao) < 10:
        return Resultado("Descreva a ocorrência com pelo menos 10 caracteres.")

    ref_final = ref_tipo_final = None
    if tipo in CATEGORIAS_COM_REFERENCIA:
        if referencia_tipo not in ReferenciaTipo.values:
            return Resultado("Escolha a referência: Nota Fiscal, Pedido ou Picking.")
        if not referencia:
            return Resultado(f"Informe o {REFERENCIA_FORM[referencia_tipo]['campo'].lower()}.")
        ref_final, ref_tipo_final = referencia[:80], referencia_tipo
    elif referencia and referencia_tipo in ReferenciaTipo.values:
        # Opcional (ex.: Reclamação/Sugestão): salva se foi preenchida.
        ref_final, ref_tipo_final = referencia[:80], referencia_tipo

    preparados = []
    if eh_produtos:
        preparados, erro = _preparar_itens(dados.get("itens_json"))
        if erro:
            return Resultado(erro)
        if not preparados:
            return Resultado("Adicione ao menos um produto (com código).")

    erro = validar_arquivos(arquivos)
    if erro:
        return Resultado(erro)

    # Pelo menos 1 foto quando há item que exige evidência visual — a mesma
    # foto pode cobrir vários itens.
    precisa_foto = any(p["categoria"] in CATEGORIAS_EXIGEM_FOTO for p in preparados)
    if precisa_foto and not any((a.content_type or "").startswith("image/") for a in arquivos):
        return Resultado(
            "Anexe pelo menos uma foto mostrando a avaria/produto vencido/volume trocado. "
            "PDF e planilha podem ir junto, mas não substituem a foto."
        )

    with transaction.atomic():
        oc = Ocorrencia(
            cliente=user,
            tipo=tipo,
            descricao=descricao,
            referencia=ref_final,
            referencia_tipo=ref_tipo_final,
        )
        oc.save(por=user)
        OcorrenciaItem.objects.bulk_create([OcorrenciaItem(ocorrencia=oc, **p) for p in preparados])

    falhas = _salvar_anexos(oc, arquivos, user)

    # Reclamação/sugestão: avisa os responsáveis de setor (best-effort).
    if tipo == "reclamacao_sugestao":
        for c in ContatoEncaminhamento.objects.filter(ativo=True):
            emails.enviar_email(
                c.email,
                f"Nova reclamação/sugestão — Ocorrência {oc.protocolo}",
                emails.layout_email(
                    f"Ocorrência {oc.protocolo}",
                    f"Uma nova reclamação/sugestão foi registrada por {escape(user.nome)}.",
                    f"/operacao/{oc.id}",
                ),
            )

    return Resultado(dados={"ocorrencia": oc, "anexos_falha": len(falhas)})


def aprovar_resolucao(user, oc) -> bool:
    """Só quem abriu aprova, e só se ainda estiver 'resolvida'."""
    with transaction.atomic():
        oc = Ocorrencia.objects.select_for_update().get(pk=oc.pk)
        if oc.cliente_id != user.pk or oc.status != Status.RESOLVIDA or oc.excluida_em:
            return False
        oc.status = Status.CONCLUIDA
        oc.aprovada_por = user
        oc.aprovada_em = timezone.now()
        oc.save(por=user)
    return True


def reabrir(user, oc) -> bool:
    """Reabrir volta para "Em tratativa" (cliente dono ou operação)."""
    if oc.excluida_em or not (user.eh_operacao or oc.cliente_id == user.pk):
        return False
    oc.status = Status.EM_ANALISE
    oc.arquivada_em = None
    oc.save(por=user)
    return True


def adicionar_mensagem(user, oc, conteudo: str, interna: bool, arquivos) -> Resultado:
    conteudo = (conteudo or "").strip()
    # Nota interna: só a operação pode marcar; o cliente nunca vê.
    interna = bool(interna) and user.eh_operacao

    if not conteudo and not arquivos:
        return Resultado("Escreva uma mensagem ou anexe um arquivo.")
    erro = validar_arquivos(arquivos)
    if erro:
        return Resultado(erro)

    # Colegas da empresa só leem: responde quem abriu ou a operação.
    if not user.eh_operacao and oc.cliente_id != user.pk:
        return Resultado("Só quem abriu esta ocorrência pode enviar mensagens.")
    # Notas internas podem ser adicionadas mesmo com a conversa encerrada.
    if not interna and oc.status in STATUS_BLOQUEADOS:
        return Resultado("Esta ocorrência está encerrada. Reabra para enviar mensagens.")

    msg = Mensagem.objects.create(ocorrencia=oc, autor=user, conteudo=conteudo, interna=interna)

    if not interna and user.eh_operacao:
        # Mensagem do operador em ocorrência parada (aberta) → em tratativa.
        if oc.status == Status.ABERTA:
            oc.status = Status.EM_ANALISE
            oc.save(por=user)
        # E-mail ao cliente (fecha o ciclo mesmo deslogado).
        emails.enviar_email(
            oc.cliente.email,
            f"Nova resposta na ocorrência {oc.protocolo}",
            emails.layout_email(
                f"Nova resposta na ocorrência {oc.protocolo}",
                "A operação respondeu à sua ocorrência. Acesse o portal para ver e responder.",
                f"/portal/{oc.id}",
            ),
        )

    falhas = _salvar_anexos(oc, arquivos, user, mensagem=msg)
    aviso = f"Mensagem enviada, mas não foi possível anexar: {', '.join(falhas)}." if falhas else None
    return Resultado(aviso=aviso)


# ---------------------------------------------------------------- operação

# A operação NÃO define "concluida" — isso é a aprovação do cliente.
STATUS_OPERACAO = [Status.ABERTA, Status.EM_ANALISE, Status.RESOLVIDA, Status.RECUSADA]


def tem_tratativa(oc) -> bool:
    """Já existe mensagem (não interna) da operação para o cliente?"""
    return oc.mensagens.filter(interna=False).exclude(autor_id=oc.cliente_id).exists()


def atualizar_ocorrencia(user, oc, dados) -> Resultado:
    if not user.eh_operacao:
        return Resultado("Apenas a operação pode alterar ocorrências.")

    status = dados.get("status", "")
    prioridade = dados.get("prioridade", "")
    atribuido = dados.get("atribuido_a") or None
    motivo = (dados.get("motivo_recusa") or "").strip()

    if status not in STATUS_OPERACAO:
        return Resultado("Status inválido.")
    if prioridade not in Prioridade.values:
        return Resultado("Prioridade inválida.")
    if status == Status.RECUSADA and len(motivo) < 3:
        return Resultado("Informe o motivo da recusa.")

    responsavel = None
    if atribuido:
        from contas.models import Usuario

        try:
            responsavel = Usuario.objects.filter(
                pk=atribuido, papel__in=[Papel.OPERADOR, Papel.ADMIN]
            ).first()
        except ValidationError:  # id que nem é UUID (formulário adulterado)
            responsavel = None
        if responsavel is None:
            return Resultado("Responsável inválido.")

    status_antes = oc.status
    mudou_status = status != status_antes

    # Só muda de status com responsável definido e tratativa registrada.
    if mudou_status:
        faltando = []
        if responsavel is None:
            faltando.append("um responsável definido")
        if not tem_tratativa(oc):
            faltando.append("pelo menos uma mensagem registrada para o cliente")
        if faltando:
            return Resultado(f"Não é possível mudar o status: falta {' e '.join(faltando)}.")

    oc.status = status
    oc.prioridade = prioridade
    oc.atribuido_a = responsavel
    # Guarda o motivo só quando recusada; limpa ao sair de recusada.
    oc.motivo_recusa = motivo if status == Status.RECUSADA else None
    oc.save(por=user)

    if mudou_status:
        extra = ""
        if status == Status.RESOLVIDA:
            extra = " Ela aguarda sua aprovação."
        elif status == Status.RECUSADA:
            extra = f" Motivo: {escape(motivo)}"
        rotulo = STATUS_LABEL[status]
        emails.enviar_email(
            oc.cliente.email,
            f"Ocorrência {oc.protocolo}: {rotulo}",
            emails.layout_email(
                f"Ocorrência {oc.protocolo} — {rotulo}",
                f"O status da sua ocorrência mudou para <strong>{rotulo}</strong>.{extra}",
                f"/portal/{oc.id}",
            ),
        )
    return Resultado()


def solicitar_coleta(user, oc, email_transportadora: str) -> Resultado:
    if not user.eh_operacao:
        return Resultado("Apenas a operação pode solicitar coleta.")
    email = (email_transportadora or "").strip()
    if "@" not in email:
        return Resultado("Informe um e-mail válido da transportadora.")

    ref = formatar_referencia(oc.referencia_tipo, oc.referencia)
    ref_texto = f" ({escape(ref)})" if ref else ""
    enviado = emails.enviar_email(
        email,
        f"Solicitação de coleta — Ocorrência {oc.protocolo}",
        emails.layout_email(
            "Solicitação de coleta",
            f"Solicitamos a coleta referente à ocorrência <strong>{oc.protocolo}</strong>{ref_texto}. "
            "Por favor, entre em contato para agendar a retirada.",
        ),
    )
    # Registra como nota interna, para auditoria — mesmo se o e-mail falhar.
    Mensagem.objects.create(
        ocorrencia=oc,
        autor=user,
        interna=True,
        conteudo=(
            f"Solicitação de coleta enviada para {email}."
            if enviado
            else f"Solicitação de coleta registrada para {email} (envio de e-mail não confirmado — "
            "verifique a configuração de SMTP)."
        ),
    )
    return Resultado()


def purgar(ids) -> int:
    """Exclusão FÍSICA (irreversível) de ocorrências da lixeira, com os arquivos."""
    ocs = Ocorrencia.objects.filter(pk__in=ids, excluida_em__isnull=False)
    arquivos = [a.arquivo for a in Anexo.objects.filter(ocorrencia__in=ocs)]
    n = ocs.count()
    ocs.delete()  # cascata: itens, mensagens, anexos, histórico, notificações
    for f in arquivos:
        try:
            f.delete(save=False)
        except Exception as e:  # noqa: BLE001
            log.warning("[lixeira] não removeu %s: %s", f.name, e)
    return n


def arquivar_concluidas_antigas(dias: int = 30) -> int:
    """Arquiva resolvidas/recusadas paradas há mais de N dias."""
    agora = timezone.now()
    with transaction.atomic():
        ids = list(
            Ocorrencia.objects.filter(
                status__in=[Status.RESOLVIDA, Status.RECUSADA],
                arquivada_em__isnull=True,
                excluida_em__isnull=True,
                atualizado_em__lt=agora - timedelta(days=dias),
            ).values_list("pk", flat=True)
        )
        Ocorrencia.objects.filter(pk__in=ids).update(arquivada_em=agora)
        # Sem autor: quem arquivou foi o sistema (aparece na linha do tempo).
        EventoOcorrencia.objects.bulk_create(
            [EventoOcorrencia(ocorrencia_id=pk, tipo=EventoTipo.ARQUIVADA, criado_em=agora) for pk in ids]
        )
    return len(ids)
