"""Preparação de dados para os templates de detalhe da ocorrência."""


def preparar_conversa(mensagens, anexos, user, oc, rotulo_cliente: str | None):
    """
    Anota cada mensagem com `autor_rotulo`, `sou_eu` e `anexos_lista`, e
    devolve os anexos da abertura (sem mensagem). Identifica o autor sem ler o
    perfil do outro lado: compara com o usuário atual e com o dono da ocorrência.
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
        if m.sou_eu:
            m.autor_rotulo = "Você"
        elif m.autor_id == oc.cliente_id:
            m.autor_rotulo = rotulo_cliente or "Cliente"
        else:
            m.autor_rotulo = "Operação"
        m.inicial = (m.autor_rotulo.strip()[:1] or "?").upper()
        m.anexos_lista = por_msg.get(m.pk, [])
    return abertura
