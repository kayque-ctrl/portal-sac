"""Spec 025, ponto 13: transportadoras ligadas às empresas e usadas na coleta."""

import pytest

from ocorrencias import servicos
from ocorrencias.models import Mensagem, Transportadora


@pytest.fixture
def rapida(empresa):
    t = Transportadora.objects.create(nome="Rápida Log", email="coleta@rapida.com")
    t.empresas.add(empresa)
    return t


# ---------------------------------------------------------------- cadastro


def test_transportadora_aparece_pelo_nome(rapida):
    assert str(rapida) == "Rápida Log"


def test_cadastra_com_empresas(operador, empresa, outra_empresa):
    r = servicos.salvar_transportadora(
        operador,
        {"nome": " Via Sul ", "email": "agenda@viasul.com", "telefone": "", "empresas": [str(empresa.pk)]},
    )

    assert r.ok, r.erro
    t = r.dados["transportadora"]
    assert (t.nome, t.email, t.telefone) == ("Via Sul", "agenda@viasul.com", None)
    assert list(t.empresas.all()) == [empresa]


def test_editar_troca_as_empresas(operador, rapida, empresa, outra_empresa):
    r = servicos.salvar_transportadora(
        operador, {"nome": "Rápida Log", "email": "novo@rapida.com", "empresas": [str(outra_empresa.pk)]}, rapida
    )

    assert r.ok, r.erro
    rapida.refresh_from_db()
    assert rapida.email == "novo@rapida.com"
    assert list(rapida.empresas.all()) == [outra_empresa]


@pytest.mark.parametrize(
    ("dados", "erro"),
    [
        ({"nome": "", "email": "a@b.com"}, "Informe o nome da transportadora."),
        ({"nome": "X", "email": "a@b.com"}, "Informe o nome da transportadora."),
        ({"nome": "Via Sul", "email": ""}, "Informe um e-mail válido."),
        ({"nome": "Via Sul", "email": "sem-arroba"}, "Informe um e-mail válido."),
        ({"nome": "Via Sul", "email": "a@"}, "Informe um e-mail válido."),
    ],
)
def test_validacao_do_cadastro(operador, dados, erro):
    assert servicos.salvar_transportadora(operador, dados).erro == erro


def test_empresas_malformadas_sao_ignoradas(operador, empresa):
    r = servicos.salvar_transportadora(
        operador, {"nome": "Via Sul", "email": "a@viasul.com", "empresas": ["lixo", "", str(empresa.pk)]}
    )

    assert list(r.dados["transportadora"].empresas.all()) == [empresa]


def test_so_a_operacao_cadastra(cliente):
    r = servicos.salvar_transportadora(cliente, {"nome": "Via Sul", "email": "a@viasul.com"})
    assert r.erro == "Apenas a operação pode cadastrar transportadoras."


# ---------------------------------------------------------------- sugestão na coleta


def test_as_da_empresa_vem_primeiro(rapida, empresa):
    Transportadora.objects.create(nome="Aérea Express", email="a@aerea.com")
    Transportadora.objects.create(nome="Desligada", email="d@d.com", ativa=False)

    da_empresa, outras = servicos.transportadoras_para_coleta(empresa.pk)

    assert [t.nome for t in da_empresa] == ["Rápida Log"]
    assert [t.nome for t in outras] == ["Aérea Express"]


def test_cliente_sem_empresa_ve_todas_como_outras(rapida):
    da_empresa, outras = servicos.transportadoras_para_coleta(None)

    assert da_empresa == []
    assert [t.nome for t in outras] == ["Rápida Log"]


# ---------------------------------------------------------------- coleta


def test_coleta_usa_email_da_transportadora(abrir, operador, rapida, mailoutbox):
    oc = abrir()

    r = servicos.solicitar_coleta(operador, oc, "", transportadora_id=str(rapida.pk))

    assert r.ok, r.erro
    assert mailoutbox[-1].to == ["coleta@rapida.com"]
    nota = Mensagem.objects.get(ocorrencia=oc)
    assert nota.interna
    assert "Rápida Log (coleta@rapida.com)" in nota.conteudo


@pytest.mark.parametrize("valor", ["lixo", "00000000-0000-0000-0000-000000000000"])
def test_transportadora_inexistente_ou_malformada(abrir, operador, valor):
    r = servicos.solicitar_coleta(operador, abrir(), "", transportadora_id=valor)
    assert r.erro == "Transportadora inválida."


def test_transportadora_inativa_e_recusada(abrir, operador, rapida):
    rapida.ativa = False
    rapida.save()

    r = servicos.solicitar_coleta(operador, abrir(), "", transportadora_id=str(rapida.pk))

    assert r.erro == "Transportadora inválida."


def test_outro_email_continua_valendo(abrir, operador, mailoutbox):
    r = servicos.solicitar_coleta(operador, abrir(), "avulsa@transp.com", transportadora_id="")

    assert r.ok, r.erro
    assert mailoutbox[-1].to == ["avulsa@transp.com"]
