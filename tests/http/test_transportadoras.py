"""Spec 025, ponto 13: telas de transportadora e a coleta no atendimento."""

import pytest

from ocorrencias.models import Mensagem, Transportadora


@pytest.fixture
def rapida(empresa):
    t = Transportadora.objects.create(nome="Rápida Log", email="coleta@rapida.com")
    t.empresas.add(empresa)
    return t


def test_cadastrar_pela_tela_com_empresas(operador, empresa, entrar):
    r = entrar(operador).post(
        "/operacao/transportadoras",
        {"nome": "Via Sul", "email": "agenda@viasul.com", "empresas": [str(empresa.pk)]},
        follow=True,
    )

    assert "Transportadora salva." in r.content.decode()
    assert list(Transportadora.objects.get(nome="Via Sul").empresas.all()) == [empresa]


def test_erro_do_cadastro_volta_com_o_que_foi_digitado(operador, empresa, entrar):
    r = entrar(operador).post(
        "/operacao/transportadoras", {"nome": "Via Sul", "email": "invalido", "empresas": [str(empresa.pk)]}
    )

    html = r.content.decode()
    assert "Informe um e-mail válido." in html
    assert 'value="Via Sul"' in html
    assert f'value="{empresa.pk}" checked' in html
    assert not Transportadora.objects.exists()


def test_editar_mostra_os_dados_e_as_empresas_marcadas(operador, rapida, empresa, entrar):
    html = entrar(operador).get(f"/operacao/transportadoras/{rapida.pk}").content.decode()

    assert 'value="coleta@rapida.com"' in html
    assert f'value="{empresa.pk}" checked' in html


def test_editar_pela_tela(operador, rapida, outra_empresa, entrar):
    entrar(operador).post(
        f"/operacao/transportadoras/{rapida.pk}",
        {"nome": "Rápida Log", "email": "novo@rapida.com", "empresas": [str(outra_empresa.pk)]},
    )

    rapida.refresh_from_db()
    assert rapida.email == "novo@rapida.com"
    assert list(rapida.empresas.all()) == [outra_empresa]


def test_desativar_e_excluir(operador, rapida, entrar):
    http = entrar(operador)

    http.post(f"/operacao/transportadoras/{rapida.pk}/alternar")
    rapida.refresh_from_db()
    assert rapida.ativa is False

    http.post(f"/operacao/transportadoras/{rapida.pk}/excluir")
    assert not Transportadora.objects.exists()


def test_acao_desconhecida_nao_muda_nada(operador, rapida, entrar):
    entrar(operador).post(f"/operacao/transportadoras/{rapida.pk}/inventada")

    rapida.refresh_from_db()
    assert rapida.ativa is True


@pytest.mark.parametrize("url", ["/operacao/transportadoras/lixo", "/operacao/transportadoras/lixo/alternar"])
def test_id_malformado_nao_e_erro_500(operador, entrar, url):
    assert entrar(operador).post(url).status_code == 404


def test_id_inexistente_e_404(operador, entrar):
    assert entrar(operador).get("/operacao/transportadoras/00000000-0000-0000-0000-000000000000").status_code == 404


@pytest.mark.parametrize("acao", ["alternar", "excluir"])
def test_cliente_nao_altera_transportadora(cliente, rapida, entrar, acao):
    r = entrar(cliente).post(f"/operacao/transportadoras/{rapida.pk}/{acao}")

    assert r.status_code == 302
    rapida.refresh_from_db()
    assert rapida.ativa is True


def test_cliente_nao_edita_transportadora(cliente, rapida, entrar):
    entrar(cliente).post(f"/operacao/transportadoras/{rapida.pk}", {"nome": "Hack", "email": "h@h.com"})

    rapida.refresh_from_db()
    assert rapida.nome == "Rápida Log"


def test_menu_da_operacao_tem_transportadoras(operador, entrar):
    assert 'href="/operacao/transportadoras"' in entrar(operador).get("/operacao/").content.decode()


def test_empresa_mostra_as_transportadoras(operador, rapida, empresa, entrar):
    html = entrar(operador).get(f"/operacao/empresas/{empresa.pk}").content.decode()

    assert "data-transportadoras-empresa" in html
    assert "Rápida Log" in html


# ---------------------------------------------------------------- coleta no atendimento


def test_atendimento_sugere_a_transportadora_da_empresa(ocorrencia, operador, rapida, entrar):
    html = entrar(operador).get(f"/operacao/{ocorrencia.pk}").content.decode()

    assert f"escolha: '{rapida.pk}'" in html
    assert "Atendem ACME" in html
    assert f'<option value="{rapida.pk}">Rápida Log · coleta@rapida.com</option>' in html


def test_atendimento_sem_transportadora_pede_o_email(ocorrencia, operador, entrar):
    html = entrar(operador).get(f"/operacao/{ocorrencia.pk}").content.decode()

    assert "Nenhuma transportadora cadastrada." in html
    assert 'name="email_transportadora"' in html


def test_coleta_pela_tela_com_a_transportadora(ocorrencia, operador, rapida, entrar, mailoutbox):
    r = entrar(operador).post(f"/operacao/{ocorrencia.pk}/coleta", {"transportadora": str(rapida.pk)})

    assert r.url == f"/operacao/{ocorrencia.pk}"
    assert mailoutbox[-1].to == ["coleta@rapida.com"]
    assert Mensagem.objects.filter(ocorrencia=ocorrencia, interna=True, conteudo__contains="Rápida Log").exists()


def test_coleta_com_transportadora_malformada_mostra_o_erro(ocorrencia, operador, entrar):
    r = entrar(operador).post(f"/operacao/{ocorrencia.pk}/coleta", {"transportadora": "lixo"})

    assert r.status_code == 200
    assert "Transportadora inválida." in r.content.decode()
