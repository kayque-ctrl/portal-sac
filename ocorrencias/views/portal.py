"""Área do cliente (/portal)."""

import json
from urllib.parse import urlencode

from django.contrib import messages
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from .. import kpis, servicos
from ..apresentacao import preparar_conversa
from ..labels import (
    CATEGORIAS_COM_PRODUTOS,
    CATEGORIAS_COM_REFERENCIA,
    CATEGORIAS_COM_SINAL_VOLUME,
    CATEGORIAS_DISPENSAM_DADOS_PRODUTO,
    CATEGORIAS_EXIGEM_FOTO,
    ITEM_CATEGORIA_LABEL,
    ITEM_CATEGORIAS,
    ITEM_TEXTO,
    ITEM_TEXTO_PADRAO,
    STATUS_LABEL,
    STATUS_ORDEM,
    TIPO_LABEL,
    TIPOS_FORM,
    SinalVolume,
)
from ..models import Aviso, Ocorrencia
from ..permissoes import colegas_da_empresa, mensagens_visiveis, ocorrencias_visiveis
from ..planilhas import XLSX_MIME, importar_produtos, planilha_ocorrencia
from ..uploads import ACCEPT_ATTR, MAX_ANEXOS
from .comum import cliente_required


def _responsaveis(user) -> dict:
    """id do autor → nome (colegas da empresa + o próprio usuário)."""
    mapa = {str(k): v for k, v in colegas_da_empresa(user).items()}
    mapa.setdefault(str(user.pk), user.nome)
    return mapa


@cliente_required
def inicio(request):
    user = request.user
    ocorrencias = list(ocorrencias_visiveis(user).filter(excluida_em__isnull=True).order_by("-criado_em"))
    responsaveis = _responsaveis(user)

    # Metadados para o filtro no navegador (Alpine); as linhas são renderizadas aqui.
    meta = [
        {
            "id": str(o.id),
            "status": o.status,
            "tipo": o.tipo,
            "dia": timezone.localtime(o.criado_em).date().isoformat(),
            "minha": o.cliente_id == user.pk,
            "texto": f"{o.protocolo} {o.descricao}".lower(),
        }
        for o in ocorrencias
    ]
    for o in ocorrencias:
        o.minha = o.cliente_id == user.pk
        # Só quem abriu é o responsável e o único que pode aprovar.
        o.aguardando = o.minha and o.status == "resolvida"
        o.responsavel_nome = "Você" if o.minha else responsaveis.get(str(o.cliente_id), "Colega")

    # Avisos: alertas primeiro.
    avisos = sorted(Aviso.vigentes(), key=lambda a: a.tipo != "alerta")

    anexos_falha = request.GET.get("anexosFalha")
    return render(
        request,
        "ocorrencias/portal/inicio.html",
        {
            "ocorrencias": ocorrencias,
            "meta": meta,
            "tem_colegas": any(not o.minha for o in ocorrencias),
            "pendentes": sum(1 for o in ocorrencias if o.aguardando),
            "avisos": avisos,
            "avisos_meta": [{"id": str(a.id), "tipo": a.tipo} for a in avisos],
            "nova": request.GET.get("nova"),
            "anexos_falha": int(anexos_falha) if (anexos_falha or "").isdigit() else 0,
            "filtro_inicial": "aprovar" if request.GET.get("filtro") == "aprovar" else "",
            "escopos": [("empresa", "Da empresa"), ("minhas", "Minhas")],
            "chips": [("todas", "Todas")] + [(s, STATUS_LABEL[s]) for s in STATUS_ORDEM],
            "tipos_form": [(t, TIPO_LABEL[t]) for t in TIPOS_FORM],
            "rotulos_tipo": {t: TIPO_LABEL[t] for t in TIPOS_FORM},
        },
    )


@cliente_required
def dashboard(request):
    periodo = kpis.parse_periodo(request.GET.get("dias"))
    k = kpis.calcular_kpis(request.user, periodo)
    agora = timezone.now()

    sla_pct = kpis.percentual_sla(k["sla_cumpridas"], k["sla_encerradas"])
    variacao = kpis.variacao_tempo(k["tempo_medio_horas"], k["tempo_medio_horas_anterior"], k["resolvidas_no_periodo"])

    # Textos dos cartões (mesmas regras do dashboard original).
    if k["com_sla_vencido"] > 0:
        aberto_sub, aberto_tom = f"{k['com_sla_vencido']} com SLA vencido", "ruim"
    elif k["em_aberto"] > 0:
        aberto_sub, aberto_tom = "nenhuma com SLA vencido", "bom"
    else:
        aberto_sub, aberto_tom = "nada em aberto", "neutro"

    minhas = k["aguardando_aprovacao_minhas"]
    if k["aguardando_aprovacao"] == 0:
        aprov_sub = "nenhuma pendente"
    elif minhas > 0:
        aprov_sub = f"{minhas} {'é sua' if minhas == 1 else 'são suas'}"
    else:
        aprov_sub = "de outros usuários da empresa"

    resolvidas = k["resolvidas_no_periodo"]
    if variacao:
        tempo_sub = variacao["texto"]
    elif resolvidas < kpis.MIN_AMOSTRA:
        tempo_sub = (
            "sem resolvidas no período"
            if resolvidas == 0
            else f"só {resolvidas} {'resolvida' if resolvidas == 1 else 'resolvidas'} no período"
        )
    else:
        tempo_sub = ""

    semanas = kpis.barras_semanas(k["semanas"])
    n = len(semanas)
    passo = 3 if n > 8 else 1
    for i, s in enumerate(semanas):
        s["mostrar"] = i == n - 1 or (i % passo == 0 and n - 1 - i >= passo)
        s["altura"] = max(s["pct"] * 0.8, 4 if s["total"] > 0 else 0)

    for a in k["atencao"]:
        a["idade"] = kpis.rotulo_idade(a["criado_em"], agora)

    motivos = {
        modo: [{**b, "rotulo": ITEM_CATEGORIA_LABEL.get(b["categoria"], b["categoria"])} for b in kpis.barras_motivos(k["motivos"], modo)]
        for modo in ("ocorrencias", "itens")
    }

    empresa = request.user.empresa.nome if request.user.empresa_id else None
    return render(
        request,
        "ocorrencias/portal/dashboard.html",
        {
            "k": k,
            "periodo": periodo,
            "periodos": kpis.PERIODOS,
            "empresa": empresa,
            "sem_dados": kpis.sem_dados(k),
            "cartoes": [
                {"label": "Em aberto", "valor": k["em_aberto"], "sub": aberto_sub, "tom": aberto_tom},
                {
                    "label": "Aguardando aprovação",
                    "valor": k["aguardando_aprovacao"],
                    "sub": aprov_sub,
                    "tom": "alerta" if minhas > 0 else "neutro",
                },
                {
                    "label": "Tempo médio de resolução",
                    "valor": kpis.valor_tempo_medio(k["tempo_medio_horas"], resolvidas),
                    "sub": tempo_sub,
                    "tom": variacao["tom"] if variacao else "neutro",
                },
                {
                    "label": "SLA cumprido",
                    "valor": "—" if sla_pct is None else f"{sla_pct}%",
                    "sub": kpis.sub_sla(k["sla_cumpridas"], k["sla_encerradas"]),
                    "tom": kpis.tom_sla(sla_pct),
                },
            ],
            "semanas": semanas,
            "motivos": motivos,
            "modos": [("ocorrencias", "Ocorrências"), ("itens", "Itens")],
        },
    )


def _ocorrencia_visivel(request, pk) -> Ocorrencia:
    oc = (
        ocorrencias_visiveis(request.user)
        .select_related("cliente__empresa", "aprovada_por__empresa")
        .filter(pk=pk, excluida_em__isnull=True)
        .first()
    )
    if oc is None:
        raise Http404
    return oc


def _render_detalhe(request, oc, **extra):
    user = request.user
    # Ocorrência de um colega: só leitura. Quem abriu é o responsável e o único
    # que responde, anexa, aprova ou reabre.
    somente_leitura = oc.cliente_id != user.pk
    responsavel_nome = (
        colegas_da_empresa(user).get(oc.cliente_id, "um colega da empresa") if somente_leitura else user.nome
    )
    mensagens = list(mensagens_visiveis(user, oc))
    abertura = preparar_conversa(
        mensagens, oc.anexos.all(), user, oc, responsavel_nome if somente_leitura else None
    )
    contexto = {
        "oc": oc,
        "somente_leitura": somente_leitura,
        "responsavel_nome": responsavel_nome,
        "mensagens": mensagens,
        "anexos_abertura": abertura,
        "itens": list(oc.itens.all()),
        "accept": ACCEPT_ATTR,
        "max_anexos": MAX_ANEXOS,
        **extra,
    }
    return render(request, "ocorrencias/portal/detalhe.html", contexto)


@cliente_required
def detalhe(request, pk):
    return _render_detalhe(request, _ocorrencia_visivel(request, pk))


@cliente_required
@require_POST
def enviar_mensagem(request, pk):
    oc = _ocorrencia_visivel(request, pk)
    r = servicos.adicionar_mensagem(
        request.user, oc, request.POST.get("conteudo", ""), False, request.FILES.getlist("anexos")
    )
    if not r.ok:
        return _render_detalhe(request, oc, msg_erro=r.erro, msg_conteudo=request.POST.get("conteudo", ""))
    if r.aviso:
        messages.warning(request, r.aviso, extra_tags="mensagem")
    return redirect("portal:detalhe", pk=oc.pk)


@cliente_required
@require_POST
def aprovar(request, pk):
    oc = _ocorrencia_visivel(request, pk)
    if servicos.aprovar_resolucao(request.user, oc):
        messages.success(request, "Ocorrência aprovada!", extra_tags="aprovada")
    else:
        # Nada mudou (ex.: reaberta em outra aba) — não mente "aprovada".
        messages.error(
            request,
            "Não foi possível aprovar: o estado da ocorrência mudou. Atualizamos a página.",
            extra_tags="aprovar_erro",
        )
    return redirect("portal:detalhe", pk=oc.pk)


@cliente_required
@require_POST
def reabrir(request, pk):
    oc = _ocorrencia_visivel(request, pk)
    if oc.cliente_id == request.user.pk:
        servicos.reabrir(request.user, oc)
    return redirect("portal:detalhe", pk=oc.pk)


@cliente_required
def exportar(request, pk):
    oc = _ocorrencia_visivel(request, pk)
    resp = HttpResponse(planilha_ocorrencia(oc), content_type=XLSX_MIME)
    resp["Content-Disposition"] = f'attachment; filename="ocorrencia-{oc.protocolo}.xlsx"'
    resp["Cache-Control"] = "no-store"
    return resp


@cliente_required
def notificacoes(request):
    lista = list(request.user.notificacoes.order_by("-criado_em")[:50])
    # Marca como lidas as exibidas nesta página (a lista já saiu com o estado anterior).
    request.user.notificacoes.filter(pk__in=[n.pk for n in lista if not n.lida]).update(lida=True)
    return render(request, "ocorrencias/notificacoes.html", {"notificacoes": lista, "voltar": "/portal/"})


# ---------------------------------------------------------------- nova ocorrência


def _config_formulario() -> dict:
    """Constantes que o wizard (Alpine) precisa no navegador."""
    return {
        "tipos": [
            {"valor": t, "label": TIPO_LABEL[t], "ajuda": ajuda, "icone": icone}
            for t, ajuda, icone in [
                ("produtos", "Avaria, falta, sobra ou troca de volume nos itens.", "package-x"),
                ("atraso", "A entrega não chegou no prazo combinado.", "clock"),
                ("reclamacao_sugestao", "Uma reclamação, elogio ou ideia para melhorarmos.", "message-square-warning"),
            ]
        ],
        "tipoLabel": TIPO_LABEL,
        "comReferencia": [str(t) for t in CATEGORIAS_COM_REFERENCIA],
        "comProdutos": [str(t) for t in CATEGORIAS_COM_PRODUTOS],
        "categorias": [{"valor": c, "label": ITEM_CATEGORIA_LABEL[c]} for c in ITEM_CATEGORIAS],
        "categoriaLabel": ITEM_CATEGORIA_LABEL,
        "exigemFoto": CATEGORIAS_EXIGEM_FOTO,
        "dispensamDados": CATEGORIAS_DISPENSAM_DADOS_PRODUTO,
        "comSinalVolume": CATEGORIAS_COM_SINAL_VOLUME,
        "categoriaTexto": ITEM_TEXTO,
        "textoPadrao": ITEM_TEXTO_PADRAO,
        "sinaisVolume": [{"valor": v, "label": label} for v, label in SinalVolume.choices],
    }


@cliente_required
def nova(request):
    contexto = {
        "config": _config_formulario(),
        "referencias": [("nf", "Nota Fiscal"), ("pedido", "Pedido")],
        "accept": ACCEPT_ATTR,
        "max_anexos": MAX_ANEXOS,
        "inicial": None,
    }

    if request.method == "POST":
        r = servicos.criar_ocorrencia(request.user, request.POST, request.FILES.getlist("anexos"))
        if r.ok:
            oc = r.dados["ocorrencia"]
            params = {"nova": oc.protocolo}
            if r.dados["anexos_falha"]:
                params["anexosFalha"] = r.dados["anexos_falha"]
            return redirect(f"/portal/?{urlencode(params)}")

        # Volta ao formulário com o que foi preenchido (fotos precisam ser anexadas de novo).
        try:
            itens = json.loads(request.POST.get("itens_json") or "[]")
        except json.JSONDecodeError:
            itens = []
        contexto["erro"] = r.erro
        contexto["inicial"] = {
            "tipo": request.POST.get("tipo", ""),
            "refTipo": request.POST.get("referencia_tipo", ""),
            "referencia": request.POST.get("referencia", ""),
            "descricao": request.POST.get("descricao", ""),
            "itens": itens if isinstance(itens, list) else [],
        }

    return render(request, "ocorrencias/portal/nova.html", contexto)


@cliente_required
@require_GET
def verificar_duplicata(request):
    return JsonResponse({"duplicata": servicos.verificar_duplicata(request.user, request.GET.get("referencia", ""))})


@cliente_required
@require_POST
def importar(request):
    return JsonResponse(importar_produtos(request.FILES.get("file")))
