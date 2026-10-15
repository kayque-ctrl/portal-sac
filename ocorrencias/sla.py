"""Interpreta os campos de SLA para exibição (badge)."""

from dataclasses import dataclass

from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .formato import js_round


@dataclass
class SlaInfo:
    estado: str  # sem_sla | no_prazo | em_risco | vencido | pausado | cumprido | estourado
    label: str
    restante_ms: float | None


def _duracao(ms: float) -> str:
    minutos = js_round(ms / 60000)
    if minutos < 60:
        return f"{minutos} min"
    h = js_round(minutos / 60)
    if h < 48:
        return f"{h} h"
    return f"{js_round(h / 24)} d"


def _campo(oc, nome):
    return oc.get(nome) if isinstance(oc, dict) else getattr(oc, nome)


def calcular_sla(oc) -> SlaInfo:
    """
    Aceita uma Ocorrencia ou um dict com status/sla_*. O relógio pausa
    enquanto a ocorrência aguarda o cliente ('resolvida').
    """
    status = _campo(oc, "status")
    horas = _campo(oc, "sla_horas")
    prazo = _campo(oc, "sla_prazo")
    restante_banco = _campo(oc, "sla_restante_ms")
    cumprido = _campo(oc, "sla_cumprido")

    if horas is None:
        return SlaInfo("sem_sla", "Sem SLA", None)

    if status in ("concluida", "recusada"):
        if cumprido is True:
            return SlaInfo("cumprido", "SLA cumprido", None)
        if cumprido is False:
            return SlaInfo("estourado", "SLA estourado", None)
        return SlaInfo("sem_sla", "—", None)

    if status == "resolvida":
        if restante_banco is None:
            return SlaInfo("pausado", "SLA pausado", None)
        if restante_banco <= 0:
            return SlaInfo("vencido", "SLA vencido", restante_banco)
        return SlaInfo("pausado", f"Pausado · {_duracao(restante_banco)}", restante_banco)

    if not prazo:
        return SlaInfo("sem_sla", "Sem SLA", None)
    if isinstance(prazo, str):
        prazo = parse_datetime(prazo)
    rem = (prazo - timezone.now()).total_seconds() * 1000
    total = horas * 3600 * 1000
    if rem <= 0:
        return SlaInfo("vencido", f"Vencido há {_duracao(-rem)}", rem)
    if rem < total * 0.25:
        return SlaInfo("em_risco", f"Vence em {_duracao(rem)}", rem)
    return SlaInfo("no_prazo", f"Vence em {_duracao(rem)}", rem)


SLA_COR = {
    "no_prazo": "bg-green-50 text-green-700 ring-green-600/20 dark:bg-green-950/40 dark:text-green-300",
    "em_risco": "bg-amber-50 text-amber-700 ring-amber-600/20 dark:bg-amber-950/40 dark:text-amber-300",
    "vencido": "bg-red-50 text-red-700 ring-red-600/20 dark:bg-red-950/40 dark:text-red-300",
    "pausado": "bg-zinc-100 text-zinc-600 ring-zinc-500/20 dark:bg-zinc-800 dark:text-zinc-300",
    "cumprido": "bg-green-50 text-green-700 ring-green-600/20 dark:bg-green-950/40 dark:text-green-300",
    "estourado": "bg-red-50 text-red-700 ring-red-600/20 dark:bg-red-950/40 dark:text-red-300",
}

SLA_ICONE = {
    "no_prazo": "clock",
    "em_risco": "alarm-clock",
    "vencido": "triangle-alert",
    "pausado": "pause-circle",
    "cumprido": "check-circle-2",
    "estourado": "triangle-alert",
}
