"""Preparação de dados para os templates de detalhe da ocorrência."""

from .labels import PRIORIDADE_LABEL, STATUS_LABEL, EventoTipo

# Ordem de desempate quando dois itens têm o mesmo horário.
_ORDEM = {"abertura": 0, "mensagem": 1, "evento": 2}


def preparar_conversa(mensagens, anexos, user, oc, rotulo_cliente: str | None):
    """
    Anota cada mensagem com `autor_rotulo`, `sou_eu` e `anexos_lista`, e
    devolve os anexos da abertura (sem mensagem). Identifica o autor sem ler o
    perfil do outro lado: compara com o usuário atual e com o dono da ocorrência.
    Para a operação, as mensagens de outros operadores levam o nome de quem
    escreveu; o cliente vê só "Operação".
    """
    visiveis = {m.pk for m in mensagens}
    por_msg: dict = {}
    abertura = []
    for a in anexos:
        if a.mensagem_id is None:
            abertura.append(a)
        elif a.mensagem_id in visiveis:
            por_msg.setdefault(a.mensagem_id, []).append(a)

    for m in mensagens:
        m.sou_eu = m.autor_id == user.pk
        m.autor_rotulo = _rotulo(m.autor_id, m.autor if user.eh_operacao else None, user, oc, rotulo_cliente)
        m.inicial = (m.autor_rotulo.strip()[:1] or "?").upper()
        m.anexos_lista = por_msg.get(m.pk, [])
    return abertura


def _rotulo(autor_id, autor, user, oc, rotulo_cliente) -> str:
    """Quem fez: "Você", o cliente, o nome do operador (só para a operação) ou "Operação"."""
    if autor_id is None:
        return "Sistema"
    if autor_id == user.pk:
        return "Você"
    if autor_id == oc.cliente_id:
        return rotulo_cliente or "Cliente"
    return autor.nome if autor is not None else "Operação"


def _texto_evento(e) -> tuple[str, str]:
    """(ícone, frase) de um EventoOcorrencia."""
    if e.tipo == EventoTipo.RESPONSAVEL:
        if not e.para:
            return "user-x", f"Removeu o responsável ({e.de or 'usuário removido'})"
        if not e.de:
            return "user-check", f"Responsável: {e.para}"
        return "user-check", f"Responsável: {e.de} → {e.para}"
    if e.tipo == EventoTipo.PRIORIDADE:
        de, para = PRIORIDADE_LABEL.get(e.de, e.de), PRIORIDADE_LABEL.get(e.para, e.para)
        return "flag", f"Prioridade: {de} → {para}"
    icones = {
        EventoTipo.ARQUIVADA: "archive",
        EventoTipo.DESARQUIVADA: "archive-restore",
        EventoTipo.EXCLUIDA: "trash-2",
        EventoTipo.RESTAURADA: "rotate-ccw",
    }
    return icones[e.tipo], e.get_tipo_display()


def linha_do_tempo(oc, user, mensagens, anexos, rotulo_cliente: str | None = None) -> list[dict]:
    """
    A história da ocorrência numa lista só, do mais antigo ao mais novo
    (spec 021): a abertura, as mensagens (já filtradas por quem vê), as trocas
    de status e, só para a operação, os eventos internos.

    `mensagens` precisa vir de `permissoes.mensagens_visiveis`: é ela que tira
    as notas internas do cliente. Os anexos de mensagens que não estão na lista
    também ficam de fora.
    """
    abertura = preparar_conversa(mensagens, anexos, user, oc, rotulo_cliente)
    itens = [
        {
            "tipo": "abertura",
            "quando": oc.criado_em,
            "autor_rotulo": _rotulo(oc.cliente_id, None, user, oc, rotulo_cliente),
            "anexos": abertura,
        }
    ]
    itens += [{"tipo": "mensagem", "quando": m.criado_em, "m": m} for m in mensagens]

    # A primeira linha do histórico é a própria abertura.
    for h in oc.historico.exclude(de_status=None).select_related("alterado_por"):
        de, para = STATUS_LABEL.get(h.de_status, h.de_status), STATUS_LABEL.get(h.para_status, h.para_status)
        autor = h.alterado_por if user.eh_operacao else None
        itens.append(
            {
                "tipo": "evento",
                "quando": h.criado_em,
                "icone": "refresh-cw",
                "texto": f"Status: {de} → {para}",
                "autor_rotulo": _rotulo(h.alterado_por_id, autor, user, oc, rotulo_cliente),
                "interno": False,
            }
        )

    if user.eh_operacao:
        for e in oc.eventos.select_related("autor"):
            icone, texto = _texto_evento(e)
            itens.append(
                {
                    "tipo": "evento",
                    "quando": e.criado_em,
                    "icone": icone,
                    "texto": texto,
                    "autor_rotulo": _rotulo(e.autor_id, e.autor, user, oc, rotulo_cliente),
                    "interno": True,
                }
            )

    # sort é estável: no mesmo horário vale a ordem abertura → mensagem → evento.
    itens.sort(key=lambda i: (i["quando"], _ORDEM[i["tipo"]]))
    return itens
