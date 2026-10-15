"""Relógio do SLA no save() (antes: triggers) e sua interpretação para exibição."""

from datetime import timedelta

from django.utils import timezone

from ocorrencias import servicos
from ocorrencias.models import Ocorrencia, SlaRegra
from ocorrencias.sla import calcular_sla


def test_regra_mais_especifica_vence(db):
    SlaRegra.objects.create(categoria="atraso", prioridade="media", horas=10)
    SlaRegra.objects.create(categoria="atraso", prioridade=None, horas=20)

    assert SlaRegra.horas_para("atraso", "media") == 10
    assert SlaRegra.horas_para("atraso", "alta") == 24  # prioridade pesa mais que tipo
    assert SlaRegra.horas_para("produtos", "baixa") == 120


def test_sla_pausa_ao_aguardar_aprovacao(abrir, responder, operador):
    oc = responder(abrir())

    oc.status = "resolvida"
    oc.save(por=operador)

    assert oc.sla_prazo is None
    assert oc.sla_restante_ms > 0
    assert calcular_sla(oc).estado == "pausado"


def test_sla_retoma_ao_reabrir(abrir, responder, operador, cliente):
    oc = responder(abrir())
    oc.status = "resolvida"
    oc.save(por=operador)

    assert servicos.reabrir(cliente, oc)

    assert oc.sla_prazo is not None
    assert oc.sla_restante_ms is None


def test_aprovar_dentro_do_prazo_marca_cumprido(abrir, responder, operador, cliente):
    oc = responder(abrir())
    oc.status = "resolvida"
    oc.save(por=operador)

    assert servicos.aprovar_resolucao(cliente, oc)

    oc.refresh_from_db()
    assert oc.status == "concluida"
    assert oc.sla_cumprido
    assert oc.aprovada_por == cliente
    assert calcular_sla(oc).estado == "cumprido"


def test_reabertura_pelo_cliente_notifica_a_operacao(abrir, responder, operador, cliente):
    from ocorrencias.models import Notificacao

    oc = responder(abrir())
    oc.status = "resolvida"
    oc.save(por=operador)

    servicos.reabrir(cliente, oc)

    assert Notificacao.objects.filter(destinatario=operador, mensagem__contains="reaberta pelo cliente").exists()


def test_prazo_vencido_e_marcado_como_estourado_ao_encerrar(abrir, operador):
    oc = abrir()
    Ocorrencia.objects.filter(pk=oc.pk).update(sla_prazo=timezone.now() - timedelta(hours=1))
    oc.refresh_from_db()
    assert calcular_sla(oc).estado == "vencido"

    oc.status = "recusada"
    oc.motivo_recusa = "Fora do prazo"
    oc.save(por=operador)

    assert oc.sla_cumprido is False
