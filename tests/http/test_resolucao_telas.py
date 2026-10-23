"""Spec 025, ponto 11: o resumo da resolução nas telas do cliente e da operação."""

import pytest

RESUMO = "Crédito lançado na próxima fatura e reentrega agendada."


def corpo(resposta) -> str:
    return resposta.content.decode()


@pytest.fixture
def resolvida(ocorrencia, operador, entrar):
    entrar(operador).post(
        f"/operacao/{ocorrencia.pk}/atualizar",
        {"status": "resolvida", "atribuido_a": str(operador.pk), "resolucao": RESUMO},
    )
    ocorrencia.refresh_from_db()
    assert ocorrencia.status == "resolvida"
    return ocorrencia


def test_resumo_aparece_para_o_cliente(resolvida, cliente, entrar):
    html = corpo(entrar(cliente).get(f"/portal/{resolvida.pk}"))

    # Spec 030: aprovar e recusar ficam na própria solução, dentro da linha do tempo.
    aprovacao = html[html.index("data-aprovacao") :]
    aprovacao = aprovacao[: aprovacao.index("</li>")]
    assert RESUMO in aprovacao
    assert "Aprovar solução" in aprovacao and "Recusar e reabrir" in aprovacao
    assert html.count("data-aprovacao") == 1  # sem o cartão repetido acima da conversa


def test_colega_ve_o_resumo_mas_nao_aprova(resolvida, colega, entrar):
    html = corpo(entrar(colega).get(f"/portal/{resolvida.pk}"))

    assert RESUMO in html
    assert "Aprovar solução" not in html and "data-aprovacao" not in html


def test_resumo_aparece_na_linha_do_tempo_da_operacao(resolvida, operador, entrar):
    html = corpo(entrar(operador).get(f"/operacao/{resolvida.pk}"))

    assert 'data-item="solucao"' in html and RESUMO in html


def test_atendimento_tem_o_campo_do_resumo(ocorrencia, operador, entrar):
    html = corpo(entrar(operador).get(f"/operacao/{ocorrencia.pk}"))

    assert '<template x-if="pedeResumo">' in html
    assert 'name="resolucao"' in html


def test_erro_do_resumo_volta_com_o_texto_digitado(ocorrencia, operador, entrar):
    r = entrar(operador).post(
        f"/operacao/{ocorrencia.pk}/atualizar",
        {"status": "resolvida", "atribuido_a": str(operador.pk), "resolucao": "curto"},
    )

    html = corpo(r)
    assert "Escreva o resumo da resolução (pelo menos 10 caracteres)." in html
    assert "statusPedido: 'resolvida'" in html
    assert "resolucao: 'curto'" in html


def test_status_adulterado_nao_vai_para_o_javascript(ocorrencia, operador, entrar):
    r = entrar(operador).post(
        f"/operacao/{ocorrencia.pk}/atualizar",
        {"status": "');alert(1)//", "atribuido_a": str(operador.pk), "resolucao": "x');alert(2)//"},
    )

    html = corpo(r)
    assert "Status inválido." in html
    assert "alert(1)" not in html  # status fora da lista nem chega à tela
    assert "statusPedido: 'em_analise'" in html
    assert "x');alert(2)" not in html  # o resumo vai escapado para JS
    assert "x\\u0027)" in html


def test_botoes_so_na_solucao_mais_recente(resolvida, cliente, operador, entrar):
    from ocorrencias import servicos

    servicos.reabrir(cliente, resolvida)
    servicos.adicionar_mensagem(operador, resolvida, "Ajustamos o crédito.", False, [])
    entrar(operador).post(
        f"/operacao/{resolvida.pk}/atualizar",
        {"status": "resolvida", "atribuido_a": str(operador.pk), "resolucao": "Crédito corrigido na fatura."},
    )

    html = corpo(entrar(cliente).get(f"/portal/{resolvida.pk}"))

    assert html.count('data-item="solucao"') == 2
    assert html.count("Aprovar solução") == 1
    assert html.index("Crédito corrigido na fatura.") > html.index("data-aprovacao") > html.index(RESUMO)


def test_resolvida_sem_resumo_ainda_mostra_os_botoes(ocorrencia, cliente, operador, entrar):
    """Ocorrência resolvida antes do resumo existir: sem solução na linha do tempo."""
    ocorrencia.status = "resolvida"
    ocorrencia.save(por=operador)

    html = corpo(entrar(cliente).get(f"/portal/{ocorrencia.pk}"))

    assert 'data-item="solucao"' not in html
    assert html.count("data-aprovacao") == 1 and "Aprovar solução" in html


def test_operacao_nao_ve_botoes_de_aprovar(resolvida, operador, entrar):
    html = corpo(entrar(operador).get(f"/operacao/{resolvida.pk}"))
    assert "Aprovar solução" not in html and "data-aprovacao" not in html
