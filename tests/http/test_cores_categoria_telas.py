"""Spec 006 nas telas: a cor da categoria aparece na lista de produtos e no formulário."""

import json

import pytest

from ocorrencias import labels, servicos

from ..builders import dados_produtos, foto


def abrir_com(cliente, categoria):
    itens = [{"categoria": categoria, "codigo": "1", "descricao": "Produto X", "quantidade": 1}]
    return servicos.criar_ocorrencia(cliente, dados_produtos(itens_json=json.dumps(itens)), [foto()]).dados["ocorrencia"]


@pytest.mark.parametrize("categoria", ["avaria", "pre_vencido", "vencido"])
def test_descricao_usa_a_cor_da_categoria_no_portal_e_na_operacao(cliente, operador, entrar, categoria):
    oc = abrir_com(cliente, categoria)
    esperado = f'<span class="min-w-0 truncate {labels.ITEM_TEXTO[categoria]}">'

    for usuario, url in ((cliente, f"/portal/{oc.pk}"), (operador, f"/operacao/{oc.pk}")):
        assert esperado in entrar(usuario).get(url).content.decode()


@pytest.mark.parametrize("categoria", ["falta", "sobra"])
def test_demais_categorias_mantem_o_texto_padrao(cliente, entrar, categoria):
    oc = abrir_com(cliente, categoria)
    html = entrar(cliente).get(f"/portal/{oc.pk}").content.decode()
    assert f'<span class="min-w-0 truncate {labels.ITEM_TEXTO_PADRAO}">' in html


def test_formulario_recebe_o_mapa_de_cores_para_o_extrato(cliente, entrar):
    config = entrar(cliente).get("/portal/nova").context["config"]
    assert config["categoriaTexto"] == labels.ITEM_TEXTO
    assert config["textoPadrao"] == labels.ITEM_TEXTO_PADRAO
