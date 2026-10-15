"""Lógica pura do painel do cliente (spec 011): sem banco, sem HTTP."""

from datetime import datetime, timezone

import pytest

from ocorrencias.kpis import (
    MIN_AMOSTRA,
    barras_motivos,
    barras_semanas,
    formatar_duracao,
    parse_periodo,
    percentual_sla,
    rotulo_idade,
    sem_dados,
    sub_sla,
    tom_sla,
    valor_tempo_medio,
    variacao_tempo,
)


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [("7", 7), ("90", 90), ("15", 30), (None, 30), ("abc", 30)],
)
def test_parse_periodo_aceita_so_7_30_90(entrada, esperado):
    assert parse_periodo(entrada) == esperado


@pytest.mark.parametrize(
    ("horas", "esperado"),
    [(None, "—"), (0.5, "30 min"), (0, "1 min"), (5.25, "5,3 h"), (30, "30 h"), (48, "2,0 d"), (72, "3,0 d")],
)
def test_formatar_duracao(horas, esperado):
    assert formatar_duracao(horas) == esperado


def test_tempo_medio_exige_amostra_minima():
    assert valor_tempo_medio(48, MIN_AMOSTRA - 1) == "—"
    assert valor_tempo_medio(48, MIN_AMOSTRA) == "2,0 d"
    assert valor_tempo_medio(None, 10) == "—"


@pytest.mark.parametrize(
    ("atual", "anterior", "resolvidas", "esperado"),
    [
        (24, 48, 10, {"texto": "24 h melhor que antes", "tom": "bom"}),
        (120, 48, 10, {"texto": "3,0 d pior que antes", "tom": "ruim"}),
        (24, None, 10, None),
        (24, 48, 2, None),
    ],
)
def test_variacao_do_tempo_menor_e_melhor(atual, anterior, resolvidas, esperado):
    assert variacao_tempo(atual, anterior, resolvidas) == esperado


def test_variacao_pequena_e_neutra():
    assert variacao_tempo(48.2, 48, 10)["tom"] == "neutro"


@pytest.mark.parametrize(
    ("cumpridas", "encerradas", "esperado"),
    [(3, 4, None), (18, 21, 86), (5, 5, 100)],
)
def test_percentual_sla_so_com_amostra_minima(cumpridas, encerradas, esperado):
    assert percentual_sla(cumpridas, encerradas) == esperado


@pytest.mark.parametrize(
    ("cumpridas", "encerradas", "esperado"),
    [
        (0, 0, "sem encerradas no período"),
        (1, 2, "só 2 encerradas no período"),
        (1, 1, "só 1 encerrada no período"),
        (18, 21, "18 de 21 no prazo"),
    ],
)
def test_texto_do_sla(cumpridas, encerradas, esperado):
    assert sub_sla(cumpridas, encerradas) == esperado


@pytest.mark.parametrize(
    ("pct", "esperado"),
    [(None, "neutro"), (95, "bom"), (80, "alerta"), (60, "ruim")],
)
def test_tom_do_sla(pct, esperado):
    assert tom_sla(pct) == esperado


MOTIVOS = [
    {"categoria": "falta", "ocorrencias": 1, "itens": 2},
    {"categoria": "avaria", "ocorrencias": 2, "itens": 6},
    {"categoria": "sobra", "ocorrencias": 0, "itens": 0},
]


def test_barras_de_motivos_por_ocorrencia_descartam_zeros_e_ordenam():
    barras = barras_motivos(MOTIVOS, "ocorrencias")
    assert [(b["categoria"], b["valor"], b["pct"]) for b in barras] == [("avaria", 2, 100), ("falta", 1, 50)]


def test_barras_de_motivos_por_item():
    barras = barras_motivos(MOTIVOS, "itens")
    assert barras[0]["categoria"] == "avaria"
    assert barras[1]["pct"] == 33


def test_barras_de_motivos_vazias():
    assert barras_motivos([], "itens") == []


def test_barras_por_semana_proporcionais_ao_maior():
    barras = barras_semanas(
        [
            {"semana": "2026-09-07", "total": 2},
            {"semana": "2026-09-14", "total": 4},
            {"semana": "2026-09-21", "total": 0},
        ]
    )
    assert [(b["rotulo"], b["total"], b["pct"]) for b in barras] == [("07/09", 2, 50), ("14/09", 4, 100), ("21/09", 0, 0)]


def test_barras_por_semana_todas_zeradas_nao_dividem_por_zero():
    assert barras_semanas([{"semana": "2026-09-07", "total": 0}])[0]["pct"] == 0


@pytest.mark.parametrize(
    ("criado_em", "esperado"),
    [
        (datetime(2026, 9, 21, 11, 40, tzinfo=timezone.utc), "agora"),
        (datetime(2026, 9, 21, 7, tzinfo=timezone.utc), "5 h"),
        (datetime(2026, 9, 15, 12, tzinfo=timezone.utc), "6 d"),
    ],
)
def test_rotulo_de_idade(criado_em, esperado):
    agora = datetime(2026, 9, 21, 12, tzinfo=timezone.utc)
    assert rotulo_idade(criado_em, agora) == esperado


VAZIO = {
    "em_aberto": 0,
    "aguardando_aprovacao": 0,
    "novas_no_periodo": 0,
    "resolvidas_no_periodo": 0,
    "sla_encerradas": 0,
}


@pytest.mark.parametrize(
    ("alteracao", "esperado"),
    [({}, True), ({"em_aberto": 1}, False), ({"sla_encerradas": 1}, False)],
)
def test_sem_dados(alteracao, esperado):
    assert sem_dados({**VAZIO, **alteracao}) is esperado
