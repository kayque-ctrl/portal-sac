"""Spec 030: visual minimalista e conversa estilo WhatsApp nas telas."""

import re

from ocorrencias import servicos


def corpo(resposta) -> str:
    return resposta.content.decode()


def classes_do_item(html: str, texto: str) -> str:
    """As classes do <li> da conversa que contém o texto."""
    fim = html.index(texto)
    inicio = html.rindex("<li ", 0, fim)
    return re.search(r'class="([^"]*)"', html[inicio:fim]).group(1)


def test_no_portal_o_cliente_fica_a_direita(ocorrencia, cliente, entrar):
    servicos.adicionar_mensagem(cliente, ocorrencia, "Mensagem do cliente.", False, [])

    html = corpo(entrar(cliente).get(f"/portal/{ocorrencia.pk}"))

    assert "eu" in classes_do_item(html, "Mensagem do cliente.").split()
    assert "eu" not in classes_do_item(html, "Olá, vamos verificar.").split()  # resposta da operação
    assert "eu" in classes_do_item(html, "abriu a ocorrência").split()


def test_colega_que_so_le_ve_o_lado_do_cliente_a_direita(ocorrencia, cliente, colega, entrar):
    servicos.adicionar_mensagem(cliente, ocorrencia, "Mensagem do cliente.", False, [])

    html = corpo(entrar(colega).get(f"/portal/{ocorrencia.pk}"))

    assert "eu" in classes_do_item(html, "Mensagem do cliente.").split()
    assert "Ana Cliente" in html  # o nome de quem escreveu aparece no balão


def test_na_mesa_a_operacao_fica_a_direita(ocorrencia, cliente, operador, admin, entrar):
    servicos.adicionar_mensagem(cliente, ocorrencia, "Mensagem do cliente.", False, [])
    servicos.adicionar_mensagem(admin, ocorrencia, "Nota do admin.", True, [])

    html = corpo(entrar(operador).get(f"/operacao/{ocorrencia.pk}"))

    assert "eu" not in classes_do_item(html, "Mensagem do cliente.").split()
    assert "eu" in classes_do_item(html, "Olá, vamos verificar.").split()
    nota = classes_do_item(html, "Nota do admin.").split()
    assert "eu" in nota and "nota" in nota
    assert "<strong>Alice Admin</strong>" in html  # outro operador: o nome aparece


def test_documento_fica_do_lado_de_quem_enviou(ocorrencia, cliente, entrar):
    html = corpo(entrar(cliente).get(f"/portal/{ocorrencia.pk}"))
    assert "doc-item outro" in html  # resp.png, enviado pela operação


def test_cliente_tem_barra_de_topo_com_abrir_ocorrencia(cliente, entrar):
    html = corpo(entrar(cliente).get("/portal/"))
    topo = html[html.index('class="topbar"') : html.index("</header>", html.index('class="topbar"'))]
    assert 'href="/portal/nova"' in topo and "data-sino" in topo


def test_operacao_tem_busca_global_no_topo(operador, entrar):
    html = corpo(entrar(operador).get("/operacao/painel"))
    assert 'action="/operacao/" role="search"' in html and 'name="q"' in html
