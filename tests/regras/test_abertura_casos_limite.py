"""Abertura de ocorrência: entradas malformadas e caminhos de borda."""

import json
from unittest import mock

import pytest

from ocorrencias import servicos
from ocorrencias.models import Anexo

from ..builders import dados_produtos, dados_reclamacao, foto


@pytest.mark.parametrize("itens_json", ["isto nao e json", "{}", '"texto"', None, "[]"])
def test_itens_malformados_equivalem_a_lista_vazia(cliente, itens_json):
    r = servicos.criar_ocorrencia(cliente, dados_produtos(itens_json=itens_json), [])
    assert r.erro == "Adicione ao menos um produto (com código)."


def test_limite_de_itens_por_ocorrencia(cliente):
    itens = [{"categoria": "falta", "codigo": str(i), "descricao": "x", "quantidade": 1} for i in range(servicos.MAX_ITENS + 1)]
    r = servicos.criar_ocorrencia(cliente, dados_produtos(itens_json=json.dumps(itens)), [])
    assert r.erro == f"Máximo de {servicos.MAX_ITENS} produtos por ocorrência. Reduza a lista."


@pytest.mark.parametrize(
    "item",
    [
        "texto solto",
        {"categoria": "inexistente", "codigo": "1", "descricao": "x", "quantidade": 1},
        {"categoria": "falta", "codigo": "", "descricao": "x", "quantidade": 1},
        {"categoria": "falta", "codigo": "1", "descricao": "", "quantidade": 1},
        {"categoria": "falta", "codigo": "1", "descricao": "x", "quantidade": 0},
        {"categoria": "falta", "codigo": "1", "descricao": "x", "quantidade": "abc"},
    ],
)
def test_item_invalido_e_descartado(cliente, item):
    r = servicos.criar_ocorrencia(cliente, dados_produtos(itens_json=json.dumps([item])), [])
    assert r.erro == "Adicione ao menos um produto (com código)."


def test_item_invalido_nao_derruba_os_validos(cliente):
    itens = [
        {"categoria": "falta", "codigo": "", "descricao": "sem codigo", "quantidade": 1},
        {"categoria": "falta", "codigo": "2", "descricao": "ok", "quantidade": 3},
    ]
    r = servicos.criar_ocorrencia(cliente, dados_produtos(itens_json=json.dumps(itens)), [])
    assert [i.codigo for i in r.dados["ocorrencia"].itens.all()] == ["2"]


def test_reclamacao_aceita_referencia_opcional(cliente):
    r = servicos.criar_ocorrencia(cliente, dados_reclamacao(referencia_tipo="nf", referencia="555"), [])
    oc = r.dados["ocorrencia"]
    assert (oc.referencia_tipo, oc.referencia) == ("nf", "555")


def test_reclamacao_sem_referencia_e_valida(cliente):
    oc = servicos.criar_ocorrencia(cliente, dados_reclamacao(), []).dados["ocorrencia"]
    assert oc.referencia is None


def test_referencia_e_truncada_em_80_caracteres(cliente):
    r = servicos.criar_ocorrencia(cliente, dados_reclamacao(referencia_tipo="pedido", referencia="9" * 200), [])
    assert len(r.dados["ocorrencia"].referencia) == 80


def test_falha_ao_salvar_anexo_nao_cancela_a_ocorrencia(cliente):
    with mock.patch.object(Anexo.objects, "create", side_effect=OSError("disco cheio")):
        r = servicos.criar_ocorrencia(cliente, dados_produtos("avaria"), [foto("a.png")])

    assert r.ok
    assert r.dados["anexos_falha"] == 1
    assert r.dados["ocorrencia"].anexos.count() == 0


def test_mensagem_com_anexo_que_falha_avisa_mas_envia(abrir, cliente):
    oc = abrir()
    with mock.patch.object(Anexo.objects, "create", side_effect=OSError("disco cheio")):
        r = servicos.adicionar_mensagem(cliente, oc, "veja", False, [foto("a.png")])

    assert r.ok
    assert "não foi possível anexar: a.png" in r.aviso
    assert oc.mensagens.count() == 1


def test_mensagem_recusa_anexo_invalido(abrir, cliente):
    from django.core.files.uploadedfile import SimpleUploadedFile

    ruim = SimpleUploadedFile("virus.exe", b"MZ", content_type="application/x-msdownload")
    r = servicos.adicionar_mensagem(cliente, abrir(), "oi", False, [ruim])
    assert r.erro == '"virus.exe" tem um formato não permitido.'
