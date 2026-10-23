"""Spec 004: na troca de volume, o cliente informa se o volume falta ou sobra."""

import json

import pytest

from ocorrencias import servicos
from ocorrencias.models import OcorrenciaItem

from ..builders import dados_produtos, foto

ERRO = "Na troca de volume, informe se o volume está faltando ou sobrando."


def troca(**extra):
    return {"categoria": "troca_volume", "codigo": "", "descricao": "", "quantidade": 1, **extra}


def abrir_com(cliente, *itens):
    return servicos.criar_ocorrencia(cliente, dados_produtos(itens_json=json.dumps(list(itens))), [foto()])


@pytest.mark.parametrize("sinal", ["falta", "sobra"])
def test_troca_de_volume_guarda_o_sinal(cliente, sinal):
    r = abrir_com(cliente, troca(sinal_volume=sinal))

    assert r.ok, r.erro
    assert r.dados["ocorrencia"].itens.get().sinal_volume == sinal


@pytest.mark.parametrize("sinal", [None, "", "talvez", 1])
def test_troca_de_volume_sem_sinal_valido_e_recusada(cliente, sinal):
    """Mesmo com o formulário burlado: a regra vale no servidor."""
    r = abrir_com(cliente, troca(sinal_volume=sinal))
    assert r.erro == ERRO


def test_um_item_sem_sinal_recusa_a_ocorrencia_toda(cliente):
    r = abrir_com(
        cliente,
        {"categoria": "falta", "codigo": "1", "descricao": "Camisa", "quantidade": 1},
        troca(),
    )
    assert r.erro == ERRO
    assert not OcorrenciaItem.objects.exists()


@pytest.mark.parametrize("categoria", ["avaria", "falta", "sobra", "vencido", "pre_vencido"])
def test_sinal_e_descartado_nas_outras_categorias(cliente, categoria):
    r = abrir_com(
        cliente, {"categoria": categoria, "codigo": "1", "descricao": "X", "quantidade": 1, "sinal_volume": "sobra"}
    )
    assert r.dados["ocorrencia"].itens.get().sinal_volume is None


@pytest.mark.parametrize(
    ("sinal", "esperado_sinal", "esperado_rotulo"),
    [
        ("falta", "neg", "Troca de volume (falta)"),
        ("sobra", "pos", "Troca de volume (sobra)"),
        (None, "neutro", "Troca de volume"),  # itens antigos, de antes da spec
    ],
)
def test_item_expoe_sinal_e_rotulo(abrir, sinal, esperado_sinal, esperado_rotulo):
    oc = abrir()
    item = OcorrenciaItem.objects.create(
        ocorrencia=oc, categoria="troca_volume", descricao="V", quantidade=1, sinal_volume=sinal
    )
    assert (item.sinal, item.rotulo_categoria) == (esperado_sinal, esperado_rotulo)


def test_exportacao_mostra_o_sinal_da_troca(cliente):
    from io import BytesIO

    from openpyxl import load_workbook

    from ocorrencias.planilhas import planilha_ocorrencia

    oc = abrir_com(cliente, troca(sinal_volume="falta")).dados["ocorrencia"]

    produtos = load_workbook(BytesIO(planilha_ocorrencia(oc)))["Produtos"]

    assert produtos["A2"].value == "Troca de volume (falta)"
