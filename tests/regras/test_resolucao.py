"""Spec 025: resumo da resolução (ponto 11) e prioridade fora das telas (ponto 12)."""

import pytest

from ocorrencias import servicos
from ocorrencias.models import HistoricoStatus

RESUMO = "Crédito lançado na próxima fatura e reentrega agendada."


@pytest.fixture
def pronta(abrir, responder):
    """Em tratativa, com resposta ao cliente: pode mudar de status."""
    return responder(abrir())


def _resolver(operador, oc, **extra):
    return servicos.atualizar_ocorrencia(
        operador, oc, {"status": "resolvida", "atribuido_a": str(operador.pk), **extra}
    )


def test_resolver_exige_resumo(pronta, operador):
    r = _resolver(operador, pronta)

    assert r.erro == "Escreva o resumo da resolução (pelo menos 10 caracteres)."
    pronta.refresh_from_db()
    assert pronta.status == "em_analise"


@pytest.mark.parametrize("resumo", ["", "   ", "curto", "123456789"])
def test_resumo_curto_e_recusado(pronta, operador, resumo):
    assert _resolver(operador, pronta, resolucao=resumo).erro == (
        "Escreva o resumo da resolução (pelo menos 10 caracteres)."
    )


def test_resumo_fica_no_historico_da_troca(pronta, operador):
    r = _resolver(operador, pronta, resolucao=f"  {RESUMO}  ")

    assert r.ok, r.erro
    h = HistoricoStatus.objects.get(ocorrencia=pronta, para_status="resolvida")
    assert h.observacao == RESUMO


def test_resumo_vai_no_email(pronta, operador, mailoutbox):
    mailoutbox.clear()

    _resolver(operador, pronta, resolucao=RESUMO)

    assert RESUMO in mailoutbox[-1].body


def test_resumo_so_e_exigido_ao_ir_para_aguardando_aprovacao(pronta, operador):
    r = servicos.atualizar_ocorrencia(operador, pronta, {"status": "em_analise", "atribuido_a": str(operador.pk)})

    assert r.ok, r.erro


def test_salvar_ja_resolvida_nao_pede_resumo_de_novo(pronta, operador):
    _resolver(operador, pronta, resolucao=RESUMO)
    pronta.refresh_from_db()

    r = _resolver(operador, pronta)

    assert r.ok, r.erro
    assert HistoricoStatus.objects.filter(ocorrencia=pronta, para_status="resolvida").count() == 1


def test_sem_prioridade_mantem_a_atual(pronta, operador):
    pronta.prioridade = "alta"
    pronta.save(por=operador)

    r = servicos.atualizar_ocorrencia(operador, pronta, {"status": "em_analise", "atribuido_a": str(operador.pk)})

    assert r.ok, r.erro
    pronta.refresh_from_db()
    assert pronta.prioridade == "alta"


def test_prioridade_invalida_continua_recusada(pronta, operador):
    r = servicos.atualizar_ocorrencia(
        operador, pronta, {"status": "em_analise", "atribuido_a": str(operador.pk), "prioridade": "urgente"}
    )

    assert r.erro == "Prioridade inválida."
