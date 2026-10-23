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


def test_atendimento_tem_filtros_da_linha_do_tempo(ocorrencia, operador, entrar):
    html = corpo(entrar(operador).get(f"/operacao/{ocorrencia.pk}"))

    assert "data-filtros-tl" in html and ':data-filtro="filtro"' in html
    for rotulo in ("Tudo", "Mensagens", "Notas internas", "Documentos"):
        assert f">{rotulo}</button>" in html


def test_resposta_da_operacao_tem_as_abas_do_prototipo(ocorrencia, operador, entrar):
    html = corpo(entrar(operador).get(f"/operacao/{ocorrencia.pk}"))
    abas = html[html.index('class="abas-resp"') :]
    assert abas.index("Responder ao cliente") < abas.index("Comentário interno")


def test_mensagem_enviada_nao_e_verde():
    from pathlib import Path

    css = (Path(__file__).resolve().parents[2] / "static" / "css" / "sac.css").read_text(encoding="utf-8")
    assert "--bal-eu: #e8eef8;" in css  # azul claro do sistema, não verde


def test_conteudo_ocupa_toda_a_largura():
    from pathlib import Path

    css = (Path(__file__).resolve().parents[2] / "static" / "css" / "sac.css").read_text(encoding="utf-8")
    regra = re.search(r"\.area > \.limite \{([^}]*)\}", css).group(1)
    assert "width: 100%" in regra
    assert "max-width" not in regra
    assert ".limite.estreito" not in css


def test_abrir_mostra_um_bloco_por_vez(cliente, entrar):
    html = corpo(entrar(cliente).get("/portal/nova"))

    assert "x-show=\"categoriaComProduto && secaoVisivel('produtos')\"" in html
    assert "x-show=\"secaoVisivel('anexos')\"" in html
    assert "x-show=\"secaoVisivel('desc')\"" in html
    assert ':disabled="enviando || !prontoParaEnviar"' in html  # só envia com o passo atual feito


def test_abrir_tem_coluna_de_ajuda_na_direita(cliente, entrar):
    html = corpo(entrar(cliente).get("/portal/nova"))

    assert 'aria-label="Ajuda"' in html
    assert "O que ter em mãos" in html
    assert "O que acontece depois" in html


def test_inicio_vazio_aponta_o_botao_do_topo(cliente, entrar):
    html = corpo(entrar(cliente).get("/portal/"))

    assert "Use o botão “Abrir ocorrência” para começar." in html
    assert "Escolha um assunto acima" not in html


def test_bloco_atual_tem_a_barra_inteira_e_descricao_mais_curta():
    from pathlib import Path

    css = (Path(__file__).resolve().parents[2] / "static" / "css" / "sac.css").read_text(encoding="utf-8")
    assert ".secao.atual::before" in css  # a barra cobre o cabeçalho também
    assert ".secao.atual { border-color: var(--preto); }" in css
    assert "grid-template-columns: 160px minmax(0, 360px) 90px" in css


def test_produto_sem_quadro_dentro_de_quadro(cliente, entrar):
    html = corpo(entrar(cliente).get("/portal/nova"))

    assert 'class="form-produto flex flex-col gap-3"' in html
    assert 'class="card-plano flex flex-col gap-3"' not in html
