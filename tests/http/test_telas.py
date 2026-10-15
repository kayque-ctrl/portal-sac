"""Telas renderizam (200) e mostram o conteúdo esperado."""

import pytest
from django.urls import reverse

from ocorrencias.models import Aviso

PUBLICAS = ["publico:inicio", "publico:consulta", "contas:login", "contas:esqueci_senha", "contas:definir_senha"]


@pytest.mark.parametrize("nome", PUBLICAS)
def test_paginas_publicas(client, nome):
    assert client.get(reverse(nome)).status_code == 200


@pytest.mark.parametrize(
    "url",
    ["/portal/", "/portal/dashboard", "/portal/dashboard?dias=7", "/portal/nova", "/portal/notificacoes", "/portal/{pk}"],
)
def test_telas_do_cliente(url, ocorrencia, cliente, entrar):
    r = entrar(cliente).get(url.format(pk=ocorrencia.pk))
    assert r.status_code == 200


def test_lista_do_cliente_mostra_protocolo_e_avisos(ocorrencia, cliente, entrar):
    Aviso.objects.create(titulo="Feriado", mensagem="Sem coleta na sexta.", tipo="alerta")

    corpo = entrar(cliente).get("/portal/").content.decode()

    assert ocorrencia.protocolo in corpo
    assert "Feriado" in corpo


@pytest.mark.parametrize(
    "url",
    [
        "/operacao/",
        "/operacao/?situacao=concluidas",
        "/operacao/?situacao=arquivadas",
        "/operacao/?situacao=lixeira",
        "/operacao/?q=Ana",
        "/operacao/painel",
        "/operacao/painel?empresa={empresa}&de=2020-01-01&ate=2099-12-31",
        "/operacao/empresas",
        "/operacao/empresas/{empresa}",
        "/operacao/usuarios",
        "/operacao/usuarios/{cliente}",
        "/operacao/avisos",
        "/operacao/contatos",
        "/operacao/sla",
        "/operacao/notificacoes",
        "/operacao/{pk}",
    ],
)
def test_telas_da_operacao(url, ocorrencia, empresa, cliente, admin, entrar):
    url = url.format(pk=ocorrencia.pk, empresa=empresa.pk, cliente=cliente.pk)
    assert entrar(admin).get(url).status_code == 200


def test_busca_da_operacao_acha_pelo_protocolo(ocorrencia, operador, entrar):
    corpo = entrar(operador).get(f"/operacao/?q={ocorrencia.protocolo}").content.decode()
    assert ocorrencia.protocolo in corpo


def test_colega_ve_ocorrencia_em_modo_leitura(ocorrencia, colega, entrar):
    corpo = entrar(colega).get(f"/portal/{ocorrencia.pk}").content.decode()
    assert "Somente Ana Cliente pode responder" in corpo


def test_consulta_publica_com_documento_correto(ocorrencia, client):
    r = client.post("/consulta", {"protocolo": ocorrencia.protocolo, "documento": "12345678900"})
    assert "Linha do tempo" in r.content.decode()


def test_consulta_publica_com_documento_errado(ocorrencia, client):
    r = client.post("/consulta", {"protocolo": ocorrencia.protocolo, "documento": "000"})
    assert "Protocolo não encontrado ou documento não confere." in r.content.decode()


def test_exportacao_da_ocorrencia_e_xlsx(ocorrencia, cliente, entrar):
    r = entrar(cliente).get(f"/portal/{ocorrencia.pk}/export")
    assert r["Content-Type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert r.content.startswith(b"PK")


def test_exportacao_do_painel_e_xlsx(ocorrencia, operador, entrar):
    r = entrar(operador).get("/operacao/painel/export?status=aberta")
    assert r.content.startswith(b"PK")
