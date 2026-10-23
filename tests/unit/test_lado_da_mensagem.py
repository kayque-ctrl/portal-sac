"""Spec 030: conversa estilo WhatsApp, o lado de quem vê fica à direita."""

from types import SimpleNamespace

import pytest

from ocorrencias.apresentacao import do_meu_lado

CLIENTE = SimpleNamespace(eh_operacao=False)
OPERACAO = SimpleNamespace(eh_operacao=True)


@pytest.mark.parametrize(
    ("do_cliente", "quem_ve", "a_direita"),
    [
        (True, CLIENTE, True),  # o cliente vê a própria mensagem à direita
        (False, CLIENTE, False),  # e a da operação à esquerda
        (False, OPERACAO, True),  # a operação vê as dela (qualquer operador) à direita
        (True, OPERACAO, False),  # e a do cliente à esquerda
    ],
)
def test_lado_da_mensagem(do_cliente, quem_ve, a_direita):
    assert do_meu_lado(do_cliente, quem_ve) is a_direita
