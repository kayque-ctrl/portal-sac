"""Formatação de datas, tempo relativo e tamanhos (pt-BR, horário de Brasília)."""

import math

from django.utils import timezone


def js_round(x: float) -> int:
    """Math.round do JS (meio sempre para cima), diferente do round() do Python."""
    return math.floor(x + 0.5)


def formatar_data(dt) -> str:
    """dd/mm/aaaa hh:mm"""
    if not dt:
        return ""
    return timezone.localtime(dt).strftime("%d/%m/%Y %H:%M")


def formatar_dia(dt) -> str:
    """dd/mm/aaaa"""
    if not dt:
        return ""
    return timezone.localtime(dt).strftime("%d/%m/%Y")


def formatar_hora(dt) -> str:
    """hh:mm"""
    if not dt:
        return ""
    return timezone.localtime(dt).strftime("%H:%M")


def dia_da_conversa(dt) -> str:
    """Separador de dia da linha do tempo: Hoje, Ontem ou dd/mm/aaaa."""
    if not dt:
        return ""
    dia = timezone.localtime(dt).date()
    diferenca = (timezone.localdate() - dia).days
    if diferenca == 0:
        return "Hoje"
    if diferenca == 1:
        return "Ontem"
    return dia.strftime("%d/%m/%Y")


def tempo_relativo(dt) -> str:
    """agora, há 5 min, há 2 h, há 3 d (depois de uma semana, a data)."""
    seg = js_round((timezone.now() - dt).total_seconds())
    if seg < 45:
        return "agora"
    minutos = js_round(seg / 60)
    if minutos < 60:
        return f"há {minutos} min"
    h = js_round(minutos / 60)
    if h < 24:
        return f"há {h} h"
    dias = js_round(h / 24)
    if dias < 7:
        return f"há {dias} d"
    return formatar_dia(dt)


def formatar_tamanho(n: int | None) -> str:
    if not n:
        return ""
    if n < 1024:
        return f"{n} B"
    if n < 1024 * 1024:
        return f"{n / 1024:.0f} KB"
    return f"{n / (1024 * 1024):.1f} MB"
