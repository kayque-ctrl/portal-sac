"""Spec 018: todo campo do formulário de abertura orienta o usuário.

O teste lê o HTML renderizado: um campo novo sem rótulo ou sem exemplo quebra a
suíte, para a orientação não se perder em mudanças futuras.
"""

from html.parser import HTMLParser

import pytest


class Campos(HTMLParser):
    def __init__(self):
        super().__init__()
        self.campos, self.rotulos, self.opcoes_categoria = [], set(), []
        self._no_select_categoria = False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "label" and a.get("for"):
            self.rotulos.add(a["for"])
        if tag in ("input", "select", "textarea"):
            self.campos.append((tag, a))
        if tag == "select" and a.get("id") == "categoria-produto":
            self._no_select_categoria = True
        if tag == "option" and self._no_select_categoria:
            self.opcoes_categoria.append(a)

    def handle_endtag(self, tag):
        if tag == "select":
            self._no_select_categoria = False


def visiveis(campos):
    """Campos que o usuário preenche (exclui hidden, CSRF, radios dentro de label e inputs de arquivo controlados por botão)."""
    for tag, a in campos:
        if a.get("type") in ("hidden", "radio") or "hidden" in (a.get("class") or "").split():
            continue
        if a.get("name") == "csrfmiddlewaretoken" or a.get("form") == "sem-form":
            continue
        yield tag, a


@pytest.fixture
def formulario(cliente, entrar):
    html = entrar(cliente).get("/portal/nova").content.decode()
    parser = Campos()
    parser.feed(html)
    return html, parser


def test_todo_campo_visivel_tem_rotulo_associado(formulario):
    _, p = formulario
    sem_rotulo = [a.get("id") or a.get("x-model") for _, a in visiveis(p.campos) if a.get("id") not in p.rotulos]
    assert sem_rotulo == []


@pytest.mark.parametrize("campo_id", ["quantidade-produto", "codigo-produto", "descricao-produto", "descricao"])
def test_campos_de_texto_mostram_exemplo(formulario, campo_id):
    _, p = formulario
    placeholder = next(a.get("placeholder", "") for _, a in p.campos if a.get("id") == campo_id)
    assert placeholder.startswith("Ex.:")


def test_referencia_usa_rotulo_e_exemplo_do_tipo_escolhido(formulario):
    _, p = formulario
    referencia = next(a for _, a in p.campos if a.get("id") == "referencia")
    assert referencia.get(":placeholder") == "config.referencias[refTipo].exemplo"
    assert "referencia" in p.rotulos


def test_categoria_comeca_sem_escolha(formulario):
    _, p = formulario
    primeira = p.opcoes_categoria[0]
    assert primeira.get("value") == "" and "disabled" in primeira


@pytest.mark.parametrize(
    "texto",
    [
        # Página única (spec 023): cada bloco diz o que fazer.
        "Os marcados com",  # legenda do obrigatório
        "O que aconteceu?",
        "Escolha uma opção.",
        "Escolha uma opção e digite o número que está no documento.",
        "Adicione um de cada vez.",
        "Aceita foto, PDF e planilha.",
        "Descreva o que aconteceu, quando e como",
        "de 10 caracteres mínimos",
        "Confira antes de enviar",
    ],
)
def test_instrucoes_das_etapas(formulario, texto):
    html, _ = formulario
    assert texto in html


def test_motivo_do_continuar_desabilitado_aparece_na_tela(formulario):
    """Na homologação, ninguém sabia por que não conseguia continuar: o motivo ficava só no title."""
    html, _ = formulario
    assert "data-motivo-bloqueio" in html
    assert 'x-text="motivoBloqueio"' in html
    assert ':title="motivoBloqueio"' in html


def test_motivos_estao_no_componente():
    from pathlib import Path

    js = (Path(__file__).resolve().parents[2] / "static" / "js" / "app.js").read_text(encoding="utf-8")
    assert "Para continuar, escolha o que aconteceu." in js
    assert "Para continuar, escolha a referência (Nota Fiscal, Pedido ou Picking) e informe o número." in js
    assert '"Escolha a categoria do produto."' in js
