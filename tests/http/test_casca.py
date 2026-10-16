"""Spec 022: casca das áreas internas (menu lateral, barra de baixo) e o sistema visual."""

import pytest

from ocorrencias.context_processors import MENU_ADMIN, MENU_CLIENTE, MENU_OPERACAO, _atual
from ocorrencias.templatetags.ocorrencias_tags import iniciais


def corpo(resposta) -> str:
    return resposta.content.decode()


def test_paginas_carregam_o_css_do_sistema_visual(cliente, entrar):
    assert "css/sac.css" in corpo(entrar(cliente).get("/portal/"))


def test_prazos_sla_so_aparece_no_menu_do_admin(operador, admin, entrar):
    assert "/operacao/sla" not in corpo(entrar(operador).get("/operacao/"))
    assert "Prazos (SLA)" in corpo(entrar(admin).get("/operacao/"))


def test_cliente_tem_atalho_para_abrir_ocorrencia_e_nao_ve_cadastros(cliente, entrar):
    html = corpo(entrar(cliente).get("/portal/"))
    assert "data-abrir-ocorrencia" in html
    assert "/operacao/empresas" not in html


def test_operacao_mostra_quantas_ocorrencias_estao_ativas(abrir, operador, entrar):
    abrir(), abrir()
    assert 'title="Ocorrências ativas">2<' in corpo(entrar(operador).get("/operacao/painel"))


@pytest.mark.parametrize(
    ("caminho", "esperado"),
    [
        ("/operacao/", "/operacao/"),
        ("/operacao/0b6c8a3e-0000-0000-0000-000000000000", "/operacao/"),
        ("/operacao/painel", "/operacao/painel"),
        ("/operacao/usuarios/abc", "/operacao/usuarios"),
        ("/operacao/notificacoes", None),
    ],
)
def test_item_ativo_do_menu_da_operacao(caminho, esperado):
    assert _atual(caminho, MENU_OPERACAO + [MENU_ADMIN], "/operacao/") == esperado


@pytest.mark.parametrize(
    ("caminho", "esperado"),
    [
        ("/portal/", "/portal/"),
        ("/portal/ocorrencias", "/portal/ocorrencias"),
        ("/portal/0b6c8a3e-0000-0000-0000-000000000000", "/portal/ocorrencias"),  # detalhe
        ("/portal/dashboard", "/portal/dashboard"),
    ],
)
def test_item_ativo_do_menu_do_cliente(caminho, esperado):
    assert _atual(caminho, MENU_CLIENTE, "/portal/ocorrencias") == esperado


def test_item_ativo_marcado_na_pagina(operador, entrar):
    html = corpo(entrar(operador).get("/operacao/empresas"))
    assert 'href="/operacao/empresas" class="item" aria-current="page"' in html


@pytest.mark.parametrize(
    ("nome", "esperado"),
    [("Ana Souza", "AS"), ("Otto", "O"), ("ana maria souza", "AS"), ("Ana Souza · ACME Distribuidora", "AS"), ("", "?"), (None, "?")],
)
def test_iniciais_do_avatar(nome, esperado):
    assert iniciais(nome) == esperado
