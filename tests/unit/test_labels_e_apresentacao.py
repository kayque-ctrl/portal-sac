"""Rótulos, sinais, ícones de notificação e preparo da conversa: sem banco."""

from types import SimpleNamespace

import pytest

from ocorrencias import labels, notificacoes
from ocorrencias.apresentacao import preparar_conversa


@pytest.mark.parametrize(
    ("categoria", "esperado"),
    [("falta", "neg"), ("sobra", "pos"), ("avaria", "neutro"), ("troca_volume", "neutro"), (None, "neutro")],
)
def test_sinal_da_categoria(categoria, esperado):
    assert labels.sinal_categoria(categoria) == esperado


@pytest.mark.parametrize(
    ("tipo", "referencia", "esperado"),
    [("nf", "123", "NF 123"), ("pedido", "9", "Pedido 9"), (None, "77", "77"), ("nf", "", ""), ("nf", None, "")],
)
def test_formatar_referencia(tipo, referencia, esperado):
    assert labels.formatar_referencia(tipo, referencia) == esperado


@pytest.mark.parametrize(
    ("mensagem", "icone"),
    [
        ("Nova ocorrência 2026-000001 de Ana", "file-plus-2"),
        ("Ocorrência foi reaberta pelo cliente", "rotate-ccw"),
        ("Ocorrência foi concluída (aprovada)", "check-circle-2"),
        ("Sua ocorrência foi recusada: motivo", "x-circle"),
        ("Está aguardando sua aprovação", "clock"),
        ("Nova mensagem do cliente", "message-square"),
        ("Qualquer outra coisa", "bell"),
    ],
)
def test_icone_da_notificacao_pela_mensagem(mensagem, icone):
    assert notificacoes.icone(mensagem)[0] == icone


def test_todo_status_tem_badge_ponto_e_rotulo():
    for status in labels.Status.values:
        assert labels.STATUS_BADGE[status]
        assert labels.STATUS_DOT[status]
        assert labels.STATUS_LABEL[status]


def test_em_tratativa_e_amarelo_e_distinto_de_aguardando_aprovacao():
    """Spec 010: em_analise usa yellow; resolvida (âmbar) não pode se confundir com ele."""
    assert "yellow" in labels.STATUS_BADGE["em_analise"]
    assert "yellow" in labels.STATUS_DOT["em_analise"]
    assert "amber" in labels.STATUS_BADGE["resolvida"]


def test_regras_de_troca_de_volume():
    """Spec 009."""
    assert "troca_volume" in labels.CATEGORIAS_EXIGEM_FOTO
    assert "troca_volume" in labels.CATEGORIAS_DISPENSAM_DADOS_PRODUTO


# ---------------------------------------------------------------- conversa


def msg(pk, autor_id):
    return SimpleNamespace(pk=pk, autor_id=autor_id)


def anexo(mensagem_id):
    return SimpleNamespace(mensagem_id=mensagem_id)


def test_preparar_conversa_rotula_autores_e_separa_anexos():
    oc = SimpleNamespace(cliente_id=1)
    eu = SimpleNamespace(pk=1)
    mensagens = [msg("m1", 1), msg("m2", 9)]
    anexos = [anexo(None), anexo("m2"), anexo("oculta")]

    abertura = preparar_conversa(mensagens, anexos, eu, oc, "Ana")

    assert len(abertura) == 1
    assert (mensagens[0].autor_rotulo, mensagens[0].sou_eu) == ("Você", True)
    assert (mensagens[1].autor_rotulo, mensagens[1].sou_eu) == ("Operação", False)
    assert mensagens[1].anexos_lista == [anexos[1]]
    assert mensagens[0].anexos_lista == []
    assert mensagens[1].inicial == "O"


def test_preparar_conversa_mostra_o_nome_do_cliente_para_a_operacao():
    oc = SimpleNamespace(cliente_id=1)
    operador = SimpleNamespace(pk=9)
    mensagens = [msg("m1", 1)]

    preparar_conversa(mensagens, [], operador, oc, "Ana Cliente")
    assert mensagens[0].autor_rotulo == "Ana Cliente"

    outras = [msg("m2", 1)]
    preparar_conversa(outras, [], operador, oc, None)
    assert outras[0].autor_rotulo == "Cliente"
