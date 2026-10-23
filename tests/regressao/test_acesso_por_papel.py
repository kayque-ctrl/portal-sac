"""Protege: spec 008 (níveis de acesso). Matriz papel × rota.

Se uma rota nova for criada, acrescente uma linha em ROTAS. Se o resultado de
alguma célula mudar, é uma mudança de permissão: precisa estar na spec.
"""

import pytest

ANON, CLIENTE, COLEGA, ESTRANHO, OPERADOR, ADMIN = "anon", "cliente", "colega", "estranho", "operador", "admin"
PAPEIS = [ANON, CLIENTE, COLEGA, ESTRANHO, OPERADOR, ADMIN]

# rota -> {papel: status}. Redirecionamentos (302) são o "não é a sua área".
ROTAS = {
    "/portal/": {ANON: 302, CLIENTE: 200, COLEGA: 200, ESTRANHO: 200, OPERADOR: 302, ADMIN: 302},
    "/portal/dashboard": {ANON: 302, CLIENTE: 200, COLEGA: 200, ESTRANHO: 200, OPERADOR: 302, ADMIN: 302},
    "/portal/nova": {ANON: 302, CLIENTE: 200, COLEGA: 200, ESTRANHO: 200, OPERADOR: 302, ADMIN: 302},
    "/portal/{pk}": {ANON: 302, CLIENTE: 200, COLEGA: 200, ESTRANHO: 404, OPERADOR: 302, ADMIN: 302},
    "/operacao/": {ANON: 302, CLIENTE: 302, COLEGA: 302, ESTRANHO: 302, OPERADOR: 200, ADMIN: 200},
    "/operacao/{pk}": {ANON: 302, CLIENTE: 302, COLEGA: 302, ESTRANHO: 302, OPERADOR: 200, ADMIN: 200},
    "/operacao/painel": {ANON: 302, CLIENTE: 302, COLEGA: 302, ESTRANHO: 302, OPERADOR: 200, ADMIN: 200},
    "/operacao/usuarios": {ANON: 302, CLIENTE: 302, COLEGA: 302, ESTRANHO: 302, OPERADOR: 200, ADMIN: 200},
    "/operacao/empresas": {ANON: 302, CLIENTE: 302, COLEGA: 302, ESTRANHO: 302, OPERADOR: 200, ADMIN: 200},
    "/operacao/avisos": {ANON: 302, CLIENTE: 302, COLEGA: 302, ESTRANHO: 302, OPERADOR: 200, ADMIN: 200},
    "/operacao/contatos": {ANON: 302, CLIENTE: 302, COLEGA: 302, ESTRANHO: 302, OPERADOR: 200, ADMIN: 200},
    "/operacao/transportadoras": {ANON: 302, CLIENTE: 302, COLEGA: 302, ESTRANHO: 302, OPERADOR: 200, ADMIN: 200},
    "/operacao/sla": {ANON: 302, CLIENTE: 302, COLEGA: 302, ESTRANHO: 302, OPERADOR: 302, ADMIN: 200},
}

CASOS = [
    pytest.param(rota, papel, status, id=f"{papel}-{rota}")
    for rota, por_papel in ROTAS.items()
    for papel, status in por_papel.items()
]


@pytest.mark.parametrize(("rota", "papel", "status"), CASOS)
def test_matriz_de_acesso(rota, papel, status, ocorrencia, request, client):
    if papel != ANON:
        client.force_login(request.getfixturevalue(papel))

    resposta = client.get(rota.format(pk=ocorrencia.pk))

    assert resposta.status_code == status


# Ações (POST) que só o admin pode fazer: a operação comum nunca consegue.
ACOES_SO_ADMIN = [
    "/operacao/{pk}/ciclo/excluir",
    "/operacao/lixeira/esvaziar",
    "/operacao/lixeira/excluir",
]


@pytest.mark.parametrize("rota", ACOES_SO_ADMIN)
def test_acoes_de_lixeira_sao_so_do_admin(rota, ocorrencia, operador, entrar):
    entrar(operador).post(rota.format(pk=ocorrencia.pk), {"ids": [str(ocorrencia.pk)]})

    ocorrencia.refresh_from_db()
    assert ocorrencia.excluida_em is None
