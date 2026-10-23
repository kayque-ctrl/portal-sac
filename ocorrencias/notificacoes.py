"""
Notificações in-app geradas a cada evento da ocorrência
(antes: triggers notif_nova_ocorrencia, notif_status e notif_mensagem).
"""

from contas.models import Papel, Usuario

from .labels import Status


def _operacao():
    return Usuario.objects.filter(papel__in=[Papel.OPERADOR, Papel.ADMIN], is_active=True)


def _para_operacao(oc, texto: str):
    from .models import Notificacao

    Notificacao.objects.bulk_create([Notificacao(destinatario=u, ocorrencia=oc, mensagem=texto) for u in _operacao()])


def _para_cliente(oc, texto: str):
    from .models import Notificacao

    Notificacao.objects.create(destinatario_id=oc.cliente_id, ocorrencia=oc, mensagem=texto)


def nova_ocorrencia(oc):
    cliente = oc.cliente
    empresa = f" ({cliente.empresa.nome})" if cliente.empresa_id else ""
    _para_operacao(oc, f"Nova ocorrência {oc.protocolo} de {cliente.nome or 'cliente'}{empresa}")


def mudanca_status(oc, por):
    """Avisa a outra parte. `por` = quem mudou (None = sistema)."""
    if oc.status == Status.EM_ANALISE:
        if por is not None and por.pk == oc.cliente_id:
            _para_operacao(oc, f"Ocorrência {oc.protocolo} foi reaberta pelo cliente")
        else:
            _para_cliente(oc, f"Sua ocorrência {oc.protocolo} está em tratativa")
    elif oc.status == Status.RESOLVIDA:
        _para_cliente(oc, f"A ocorrência {oc.protocolo} está aguardando sua aprovação")
    elif oc.status == Status.CONCLUIDA:
        _para_operacao(oc, f"Ocorrência {oc.protocolo} foi concluída (aprovada pelo cliente)")
    elif oc.status == Status.RECUSADA:
        motivo = f": {oc.motivo_recusa}" if oc.motivo_recusa else ""
        _para_cliente(oc, f"Sua ocorrência {oc.protocolo} foi recusada{motivo}")


def nova_mensagem(msg):
    """Notas internas não chegam aqui (o chamador já filtra)."""
    oc = msg.ocorrencia
    if msg.autor_id == oc.cliente_id:
        _para_operacao(oc, f"Nova mensagem do cliente na ocorrência {oc.protocolo}")
    else:
        _para_cliente(oc, f"Nova resposta na sua ocorrência {oc.protocolo}")


def icone(mensagem: str) -> tuple[str, str]:
    """
    Ícone (lucide) e cor da notificação. Como não há um campo "tipo",
    inferimos pela mensagem.
    """
    m = mensagem.lower()
    if "nova ocorrência" in m:
        return "file-plus-2", "text-blue-500"
    if "reaberta" in m or "reabriu" in m:
        return "rotate-ccw", "text-sky-500"
    if "concluíd" in m or "aprovad" in m:
        return "check-circle-2", "text-green-500"
    if "recusad" in m:
        return "x-circle", "text-red-500"
    if "resolvida" in m or "aprovação" in m:
        return "clock", "text-amber-500"
    if "mensagem" in m or "resposta" in m:
        return "message-square", "text-zinc-500"
    return "bell", "text-zinc-500"
