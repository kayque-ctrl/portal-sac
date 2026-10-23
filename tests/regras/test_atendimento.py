"""Atendimento pela operação (servicos.atualizar_ocorrencia e coleta)."""

from ocorrencias import servicos
from ocorrencias.models import Mensagem

PEDIDO_RESOLVIDA = {"status": "resolvida", "prioridade": "media", "atribuido_a": ""}


def test_mudar_status_exige_responsavel_e_tratativa(abrir, operador):
    oc = abrir()

    r = servicos.atualizar_ocorrencia(operador, oc, PEDIDO_RESOLVIDA)

    assert r.erro == (
        "Não é possível mudar o status: falta um responsável definido "
        "e pelo menos uma mensagem registrada para o cliente."
    )


def test_mudar_status_com_responsavel_e_tratativa(abrir, responder, operador):
    oc = responder(abrir())

    r = servicos.atualizar_ocorrencia(
        operador, oc, {**PEDIDO_RESOLVIDA, "atribuido_a": str(operador.pk), "resolucao": "Entrega reagendada."}
    )

    assert r.ok, r.erro
    oc.refresh_from_db()
    assert oc.status == "resolvida"


def test_so_a_operacao_atualiza(abrir, cliente):
    r = servicos.atualizar_ocorrencia(cliente, abrir(), PEDIDO_RESOLVIDA)
    assert r.erro == "Apenas a operação pode alterar ocorrências."


def test_operacao_nao_define_concluida(abrir, operador):
    pedido = {"prioridade": "media", "atribuido_a": str(operador.pk), "status": "concluida"}
    assert servicos.atualizar_ocorrencia(operador, abrir(), pedido).erro == "Status inválido."


def test_recusa_exige_motivo(abrir, operador):
    pedido = {"prioridade": "media", "atribuido_a": str(operador.pk), "status": "recusada"}
    assert servicos.atualizar_ocorrencia(operador, abrir(), pedido).erro == "Informe o motivo da recusa."


def test_motivo_so_e_guardado_enquanto_recusada(abrir, responder, operador):
    oc = responder(abrir())
    base = {"prioridade": "media", "atribuido_a": str(operador.pk)}

    servicos.atualizar_ocorrencia(operador, oc, {**base, "status": "recusada", "motivo_recusa": "Fora do prazo"})
    oc.refresh_from_db()
    assert oc.motivo_recusa == "Fora do prazo"

    servicos.atualizar_ocorrencia(operador, oc, {**base, "status": "em_analise"})
    oc.refresh_from_db()
    assert oc.motivo_recusa is None


def test_responsavel_precisa_ser_da_operacao(abrir, cliente, operador):
    pedido = {"status": "aberta", "prioridade": "media", "atribuido_a": str(cliente.pk)}
    assert servicos.atualizar_ocorrencia(operador, abrir(), pedido).erro == "Responsável inválido."


def test_coleta_registra_nota_interna_para_auditoria(abrir, operador):
    oc = abrir()

    r = servicos.solicitar_coleta(operador, oc, "transp@exemplo.com")

    assert r.ok
    msg = Mensagem.objects.get(ocorrencia=oc)
    assert msg.interna
    assert "transp@exemplo.com" in msg.conteudo


def test_coleta_exige_email_valido(abrir, operador):
    assert (
        servicos.solicitar_coleta(operador, abrir(), "sem-arroba").erro == "Informe um e-mail válido da transportadora."
    )


def test_cliente_nao_solicita_coleta(abrir, cliente):
    assert servicos.solicitar_coleta(cliente, abrir(), "t@x.com").erro == "Apenas a operação pode solicitar coleta."
