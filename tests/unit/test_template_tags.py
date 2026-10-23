"""Filtros e tags de template (templatetags/ocorrencias_tags.py): sem banco."""

from datetime import UTC, datetime

import pytest
from django.http import QueryDict
from django.test import RequestFactory

from ocorrencias.templatetags import ocorrencias_tags as tags


def test_filtros_de_rotulo_devolvem_o_valor_quando_desconhecido():
    assert tags.status_label("em_analise") == "Em tratativa"
    assert tags.status_label("xyz") == "xyz"
    assert tags.tipo_label("atraso") == "Atraso na entrega"
    assert tags.categoria_label("pre_vencido") == "Pré-vencido"
    assert tags.prioridade_label("alta") == "Alta"


def test_filtros_de_cor_desconhecida_ficam_vazios_ou_neutros():
    assert tags.item_badge("xyz") == ""
    assert tags.papel_badge("xyz") == ""
    assert tags.prioridade_badge("xyz") == ""
    assert tags.status_dot("xyz") == "bg-zinc-400"


def test_filtros_de_data():
    dt = datetime(2026, 9, 21, 15, 0, tzinfo=UTC)
    assert tags.data(dt) == "21/09/2026 12:00"
    assert tags.dia(dt) == "21/09/2026"


def test_filtro_get_aceita_dict_querydict_e_ignora_o_resto():
    assert tags.get({"a": 1}, "a") == 1
    assert tags.get(QueryDict("q=abc"), "q") == "abc"
    assert tags.get(None, "a") == ""
    assert tags.get("texto", "a") == ""


@pytest.mark.parametrize(("n", "esperado"), [(0, "ocorrências"), (1, "ocorrência"), (2, "ocorrências")])
def test_plural(n, esperado):
    assert tags.plural(n, "ocorrência,ocorrências") == esperado


def test_icone_escapa_o_nome():
    html = tags.icone('x"><script>', 12)
    assert "<script>" not in html
    assert "width:12px" in html


def test_status_badge_escapa_status_desconhecido():
    assert "&lt;b&gt;" in tags.status_badge("<b>")


def test_sla_badge_vazio_sem_sla():
    assert (
        tags.sla_badge(
            {"status": "aberta", "sla_horas": None, "sla_prazo": None, "sla_restante_ms": None, "sla_cumprido": None}
        )
        == ""
    )


def test_sla_badge_com_sla():
    html = tags.sla_badge(
        {"status": "concluida", "sla_horas": 72, "sla_prazo": None, "sla_restante_ms": None, "sla_cumprido": True}
    )
    assert "SLA cumprido" in html


def test_notif_icone_usa_o_icone_da_mensagem():
    assert "file-plus-2" in tags.notif_icone("Nova ocorrência 2026-000001")


@pytest.mark.parametrize(
    ("status", "estados"),
    [
        ("aberta", ["atual", "futuro", "futuro", "futuro"]),
        ("em_analise", ["feito", "atual", "futuro", "futuro"]),
        ("concluida", ["feito", "feito", "feito", "atual"]),
        ("recusada", ["feito", "feito", "recusado"]),
        ("desconhecido", ["atual", "futuro", "futuro", "futuro"]),
    ],
)
def test_trilha_de_andamento(status, estados):
    passos = tags.andamento(status)["passos"]
    assert [p["estado"] for p in passos] == estados
    assert passos[-1]["ultimo"] is True
    assert [p["numero"] for p in passos] == list(range(1, len(passos) + 1))


def contexto(qs: str) -> dict:
    return {"request": RequestFactory().get(f"/operacao/?{qs}")}


def test_url_com_troca_e_remove_parametros():
    assert tags.url_com(contexto("q=abc&page=3"), page=4) == "?q=abc&page=4"
    assert tags.url_com(contexto("q=abc&page=3"), page="") == "?q=abc"


def test_url_com_sem_parametros_restantes():
    assert tags.url_com(contexto("page=2"), page=None) == "?"


def test_query_descarta_valores_vazios():
    assert tags.query(situacao="lixeira", q="", tipo=None) == "situacao=lixeira"
