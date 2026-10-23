"""Interpretação do SLA para o badge (sla.calcular_sla): sem banco."""

from datetime import timedelta

import pytest
from django.utils import timezone

from ocorrencias.sla import calcular_sla


def oc(status="aberta", horas=72, prazo=None, restante=None, cumprido=None):
    return {
        "status": status,
        "sla_horas": horas,
        "sla_prazo": prazo,
        "sla_restante_ms": restante,
        "sla_cumprido": cumprido,
    }


def em(horas):
    return timezone.now() + timedelta(hours=horas)


def test_sem_regra_de_sla():
    assert calcular_sla(oc(horas=None)).estado == "sem_sla"


@pytest.mark.parametrize("status", ["concluida", "recusada"])
@pytest.mark.parametrize(("cumprido", "estado"), [(True, "cumprido"), (False, "estourado"), (None, "sem_sla")])
def test_encerrada_mostra_se_cumpriu(status, cumprido, estado):
    assert calcular_sla(oc(status=status, cumprido=cumprido)).estado == estado


def test_aguardando_aprovacao_pausa_o_relogio():
    info = calcular_sla(oc(status="resolvida", restante=2 * 3600 * 1000))
    assert info.estado == "pausado"
    assert info.label == "Pausado · 2 h"


def test_aguardando_aprovacao_sem_tempo_guardado():
    assert calcular_sla(oc(status="resolvida")).label == "SLA pausado"


def test_aguardando_aprovacao_com_tempo_esgotado_esta_vencido():
    assert calcular_sla(oc(status="resolvida", restante=0)).estado == "vencido"


def test_sem_prazo_calculado():
    assert calcular_sla(oc(prazo=None)).estado == "sem_sla"


@pytest.mark.parametrize(
    ("prazo", "estado"),
    [(em(60), "no_prazo"), (em(10), "em_risco"), (em(-3), "vencido")],
)
def test_estados_do_prazo(prazo, estado):
    assert calcular_sla(oc(prazo=prazo)).estado == estado


def test_prazo_como_texto_iso():
    assert calcular_sla(oc(prazo=em(60).isoformat())).estado == "no_prazo"


@pytest.mark.parametrize(
    ("ms", "texto"),
    [(30 * 60_000, "30 min"), (5 * 3600_000, "5 h"), (72 * 3600_000, "3 d")],
)
def test_duracao_legivel(ms, texto):
    assert calcular_sla(oc(status="resolvida", restante=ms)).label == f"Pausado · {texto}"
