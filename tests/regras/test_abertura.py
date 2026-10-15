"""Abertura de ocorrência (servicos.criar_ocorrencia)."""

from unittest import mock

import pytest
from django.utils import timezone

from ocorrencias import servicos
from ocorrencias.models import ContatoEncaminhamento, HistoricoStatus, Notificacao

from ..builders import dados_atraso, dados_produtos, dados_reclamacao, foto


def test_criacao_gera_protocolo_sla_historico_e_notifica_operacao(abrir, operador, admin):
    oc = abrir()

    assert oc.protocolo.startswith(f"{timezone.localtime().year}-")
    assert len(oc.protocolo) == len("AAAA-000000")
    assert oc.status == "aberta"
    assert oc.sla_horas == 72  # padrão: prioridade média
    assert (oc.sla_prazo - oc.criado_em).total_seconds() == pytest.approx(72 * 3600, abs=5)
    assert HistoricoStatus.objects.filter(ocorrencia=oc).count() == 1
    destinatarios = set(Notificacao.objects.filter(ocorrencia=oc).values_list("destinatario_id", flat=True))
    assert destinatarios == {operador.pk, admin.pk}


def test_protocolos_sao_sequenciais(abrir):
    a, b = abrir(), abrir()
    assert int(b.protocolo.split("-")[1]) == int(a.protocolo.split("-")[1]) + 1


def test_somente_cliente_abre(operador):
    r = servicos.criar_ocorrencia(operador, dados_atraso(), [])
    assert r.erro == "Apenas clientes podem abrir ocorrências."


@pytest.mark.parametrize(
    ("extra", "erro"),
    [
        ({"tipo": "outro"}, "Selecione um tipo válido."),
        ({"descricao": "curta"}, "Descreva a ocorrência com pelo menos 10 caracteres."),
        ({"referencia_tipo": ""}, "Escolha a referência: Nota Fiscal, Pedido ou Picking."),
        ({"referencia": ""}, "Informe o número do pedido."),
    ],
)
def test_validacoes_de_abertura(cliente, extra, erro):
    r = servicos.criar_ocorrencia(cliente, dados_atraso(**extra), [])
    assert r.erro == erro


def test_produtos_exigem_ao_menos_um_item(cliente):
    r = servicos.criar_ocorrencia(cliente, dados_produtos(itens_json="[]"), [])
    assert r.erro == "Adicione ao menos um produto (com código)."


def test_avaria_exige_foto(cliente):
    r = servicos.criar_ocorrencia(cliente, dados_produtos("avaria"), [])
    assert "Anexe pelo menos uma foto" in r.erro


def test_avaria_com_foto_salva_item_e_anexo(cliente):
    r = servicos.criar_ocorrencia(cliente, dados_produtos("avaria"), [foto()])

    assert r.ok, r.erro
    oc = r.dados["ocorrencia"]
    assert oc.itens.count() == 1
    assert oc.anexos.count() == 1


def test_falta_nao_exige_foto(cliente):
    assert servicos.criar_ocorrencia(cliente, dados_produtos("falta"), []).ok


def test_troca_de_volume_exige_foto(cliente):
    dados = dados_produtos(itens_json='[{"categoria": "troca_volume", "codigo": "", "descricao": "", "quantidade": "", "sinal_volume": "falta"}]')
    r = servicos.criar_ocorrencia(cliente, dados, [])
    assert "Anexe pelo menos uma foto" in r.erro


def test_troca_de_volume_dispensa_codigo_descricao_e_quantidade(cliente):
    dados = dados_produtos(itens_json='[{"categoria": "troca_volume", "codigo": "", "descricao": "", "quantidade": "", "sinal_volume": "falta"}]')

    r = servicos.criar_ocorrencia(cliente, dados, [foto()])

    assert r.ok, r.erro
    item = r.dados["ocorrencia"].itens.get()
    assert (item.descricao, item.quantidade) == ("Troca de volume", 1)


def test_reclamacao_avisa_so_contatos_ativos(cliente):
    ContatoEncaminhamento.objects.create(email="qualidade@empresa.com")
    ContatoEncaminhamento.objects.create(email="inativo@empresa.com", ativo=False)

    with mock.patch("ocorrencias.emails.enviar_email") as enviar:
        r = servicos.criar_ocorrencia(cliente, dados_reclamacao(), [])

    assert r.ok, r.erro
    assert [c.args[0] for c in enviar.call_args_list] == ["qualidade@empresa.com"]


def test_atraso_nao_avisa_contatos(cliente):
    ContatoEncaminhamento.objects.create(email="qualidade@empresa.com")
    with mock.patch("ocorrencias.emails.enviar_email") as enviar:
        servicos.criar_ocorrencia(cliente, dados_atraso(), [])
    enviar.assert_not_called()


def test_duplicata_avisa_quem_abriu(abrir, cliente, colega, estranho):
    abrir()

    assert servicos.verificar_duplicata(cliente, "987")["abertaPor"] is None
    assert servicos.verificar_duplicata(colega, "987")["abertaPor"] == "Ana Cliente"
    assert servicos.verificar_duplicata(estranho, "987") is None
