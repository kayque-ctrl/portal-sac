"""Protege: o cliente nunca recebe nada interno na linha do tempo (spec 021).

Comentário interno, anexo de comentário interno e eventos só da operação
(responsável, prioridade, arquivamento) não podem aparecer no HTML do portal,
nem para quem abriu nem para o colega da empresa.
"""

import pytest

from ocorrencias import servicos
from ocorrencias.models import Anexo, Ocorrencia

from ..builders import foto

SEGREDO = "Cliente costuma exagerar, conferir antes."


@pytest.fixture
def com_interno(ocorrencia, operador):
    servicos.adicionar_mensagem(operador, ocorrencia, SEGREDO, True, [foto("so-operacao.png")])
    oc = Ocorrencia.objects.get(pk=ocorrencia.pk)
    oc.prioridade = "alta"
    oc.atribuido_a = operador
    oc.save(por=operador)
    oc.arquivada_em = oc.criado_em
    oc.save(por=operador)
    return oc


@pytest.mark.parametrize("quem", ["cliente", "colega"])
def test_portal_nao_mostra_nada_interno(com_interno, request, entrar, quem):
    html = entrar(request.getfixturevalue(quem)).get(f"/portal/{com_interno.pk}").content.decode()
    anexo_interno = Anexo.objects.get(nome_arquivo="so-operacao.png")

    assert SEGREDO not in html
    assert "Comentário interno" not in html
    assert "so-operacao.png" not in html and str(anexo_interno.pk) not in html
    assert 'data-item="evento-interno"' not in html
    assert "Prioridade:" not in html and "Responsável:" not in html and "Arquivada" not in html
    assert "Otto" not in html  # nome do operador também não


def test_a_operacao_ve_o_que_o_cliente_nao_ve(com_interno, operador, entrar):
    html = entrar(operador).get(f"/operacao/{com_interno.pk}").content.decode()
    assert SEGREDO in html and "so-operacao.png" in html
    assert html.count('data-item="evento-interno"') == 3
