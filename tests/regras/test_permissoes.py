"""permissoes.py: quem vê o quê (a base do controle de acesso)."""

from ocorrencias.permissoes import colegas_da_empresa, mensagens_visiveis, ocorrencias_visiveis


def test_operacao_ve_todas_as_ocorrencias(abrir, operador, admin, estranho):
    a = abrir()
    b = abrir(por=None)
    assert set(ocorrencias_visiveis(operador)) == {a, b}
    assert set(ocorrencias_visiveis(admin)) == {a, b}


def test_colegas_da_empresa_lista_so_clientes_da_mesma_empresa(cliente, colega, estranho, operador):
    assert colegas_da_empresa(cliente) == {cliente.pk: "Ana Cliente", colega.pk: "Bruno Colega"}
    assert colegas_da_empresa(estranho) == {estranho.pk: "Carla Globex"}


def test_usuario_sem_empresa_nao_tem_colegas(sem_empresa):
    assert colegas_da_empresa(sem_empresa) == {}


def test_operador_vendo_mensagens_inclui_as_internas(abrir, responder, operador):
    from ocorrencias import servicos

    oc = responder(abrir())
    servicos.adicionar_mensagem(operador, oc, "interna", True, [])
    assert mensagens_visiveis(operador, oc).count() == 2
