"""Mensagens, notificações e histórico (servicos.adicionar_mensagem)."""

from ocorrencias import servicos
from ocorrencias.models import Notificacao


def test_resposta_da_operacao_move_para_tratativa_e_notifica_o_cliente(abrir, responder, cliente):
    oc = abrir()
    Notificacao.objects.all().delete()

    responder(oc)

    assert oc.status == "em_analise"
    assert Notificacao.objects.filter(destinatario=cliente, mensagem__contains="Nova resposta").exists()


def test_mensagem_do_cliente_notifica_a_operacao(abrir, operador):
    oc = abrir()
    Notificacao.objects.all().delete()

    servicos.adicionar_mensagem(oc.cliente, oc, "Alguma novidade?", False, [])

    assert Notificacao.objects.filter(destinatario=operador, mensagem__contains="Nova mensagem do cliente").exists()


def test_mensagem_sem_texto_e_sem_anexo_e_recusada(abrir, cliente):
    r = servicos.adicionar_mensagem(cliente, abrir(), "   ", False, [])
    assert r.erro == "Escreva uma mensagem ou anexe um arquivo."


def test_conversa_encerrada_bloqueia_mensagem_publica_mas_aceita_nota_interna(abrir, cliente, operador):
    oc = abrir()
    oc.status = "recusada"
    oc.save(por=operador)

    publica = servicos.adicionar_mensagem(cliente, oc, "oi", False, [])
    interna = servicos.adicionar_mensagem(operador, oc, "registro", True, [])

    assert publica.erro == "Esta ocorrência está encerrada. Reabra para enviar mensagens."
    assert interna.ok


def test_historico_registra_cada_troca_de_status(abrir, responder):
    oc = abrir()
    responder(oc)

    trocas = list(oc.historico.values_list("de_status", "para_status"))

    assert trocas == [(None, "aberta"), ("aberta", "em_analise")]
