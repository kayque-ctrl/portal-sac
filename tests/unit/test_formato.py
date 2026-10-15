"""Formatação de datas, tempo relativo e tamanhos (formato.py)."""

from datetime import datetime, timedelta, timezone
from unittest import mock

import pytest

from ocorrencias import formato

AGORA = datetime(2026, 9, 21, 15, 0, tzinfo=timezone.utc)


@pytest.mark.parametrize(("x", "esperado"), [(0.5, 1), (1.5, 2), (2.5, 3), (-0.5, 0), (2.4, 2)])
def test_js_round_arredonda_meio_para_cima(x, esperado):
    assert formato.js_round(x) == esperado


def test_formatar_data_converte_para_horario_de_brasilia():
    assert formato.formatar_data(AGORA) == "21/09/2026 12:00"


def test_formatar_dia():
    assert formato.formatar_dia(AGORA) == "21/09/2026"


@pytest.mark.parametrize("funcao", [formato.formatar_data, formato.formatar_dia])
def test_formatos_de_data_vazia(funcao):
    assert funcao(None) == ""


@pytest.mark.parametrize(
    ("atras", "esperado"),
    [
        (timedelta(seconds=10), "agora"),
        (timedelta(minutes=5), "há 5 min"),
        (timedelta(hours=3), "há 3 h"),
        (timedelta(days=2), "há 2 d"),
        (timedelta(days=10), "11/09/2026"),
    ],
)
def test_tempo_relativo(atras, esperado):
    with mock.patch("ocorrencias.formato.timezone.now", return_value=AGORA):
        assert formato.tempo_relativo(AGORA - atras) == esperado


@pytest.mark.parametrize(
    ("n", "esperado"),
    [(None, ""), (0, ""), (500, "500 B"), (2048, "2 KB"), (5 * 1024 * 1024, "5.0 MB")],
)
def test_formatar_tamanho(n, esperado):
    assert formato.formatar_tamanho(n) == esperado
