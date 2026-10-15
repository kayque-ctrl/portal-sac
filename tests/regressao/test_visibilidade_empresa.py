"""Protege: spec 012 (visibilidade por empresa; responsável = quem abriu).

Leitura e escrita são regras separadas: ampliar quem LÊ nunca pode ampliar
quem AGE. Estas garantias substituem o RLS do projeto original.
"""

from ocorrencias import servicos
from ocorrencias.models import Mensagem
from ocorrencias.permissoes import mensagens_visiveis, ocorrencias_visiveis, pode_agir, pode_ver

from ..builders import dados_atraso


def test_colega_da_empresa_le_mas_nao_age(abrir, colega, operador):
    oc = abrir()
    assert pode_ver(colega, oc)
    assert not pode_agir(colega, oc)
    assert pode_agir(operador, oc)


def test_outra_empresa_nao_ve_nada(abrir, estranho, colega):
    oc = abrir()
    assert not pode_ver(estranho, oc)
    assert list(ocorrencias_visiveis(estranho)) == []
    assert list(ocorrencias_visiveis(colega)) == [oc]


def test_usuario_sem_empresa_ve_so_as_proprias(sem_empresa, db):
    from contas.models import Usuario

    outro_sem_empresa = Usuario.objects.create_user("solo2@x.com", "senha-forte-1", nome="Solo 2")
    oc = servicos.criar_ocorrencia(sem_empresa, dados_atraso(), [])
    oc = oc.dados["ocorrencia"]

    assert pode_ver(sem_empresa, oc)
    assert not pode_ver(outro_sem_empresa, oc)


def test_colega_nao_envia_mensagem(abrir, colega):
    r = servicos.adicionar_mensagem(colega, abrir(), "oi", False, [])
    assert r.erro == "Só quem abriu esta ocorrência pode enviar mensagens."


def test_so_quem_abriu_aprova(abrir, colega, operador, cliente):
    oc = abrir()
    oc.status = "resolvida"
    oc.save(por=operador)

    assert not servicos.aprovar_resolucao(colega, oc)
    assert not servicos.aprovar_resolucao(operador, oc)
    assert servicos.aprovar_resolucao(cliente, oc)


def test_segunda_aprovacao_nao_muda_nada(abrir, operador, cliente):
    """Aprovar de novo (ex.: outra aba) devolve False em vez de "mentir" que aprovou."""
    oc = abrir()
    oc.status = "resolvida"
    oc.save(por=operador)
    assert servicos.aprovar_resolucao(cliente, oc)

    assert not servicos.aprovar_resolucao(cliente, oc)


def test_nota_interna_nunca_aparece_para_o_cliente(abrir, operador, cliente):
    oc = abrir()
    servicos.adicionar_mensagem(operador, oc, "só nós", True, [])

    assert mensagens_visiveis(cliente, oc).count() == 0
    assert mensagens_visiveis(operador, oc).count() == 1


def test_cliente_nao_consegue_marcar_nota_interna(abrir, cliente):
    oc = abrir()
    servicos.adicionar_mensagem(cliente, oc, "oi", True, [])
    assert not Mensagem.objects.get(ocorrencia=oc).interna


def test_nota_interna_nao_move_status_nem_notifica_o_cliente(abrir, operador, cliente):
    from ocorrencias.models import Notificacao

    oc = abrir()
    Notificacao.objects.all().delete()

    assert servicos.adicionar_mensagem(operador, oc, "só nós", True, []).ok

    oc.refresh_from_db()
    assert oc.status == "aberta"
    assert not Notificacao.objects.filter(destinatario=cliente).exists()


def test_anexo_respeita_a_visibilidade(ocorrencia, colega, estranho, entrar):
    anexo = ocorrencia.anexos.first()

    assert entrar(colega).get(f"/anexos/{anexo.pk}").status_code == 200
    assert entrar(estranho).get(f"/anexos/{anexo.pk}").status_code == 404


def test_anexo_de_nota_interna_e_404_para_o_cliente(ocorrencia, operador, cliente, entrar):
    from ..builders import foto

    servicos.adicionar_mensagem(operador, ocorrencia, "foto interna", True, [foto("interna.png")])
    interno = ocorrencia.anexos.get(mensagem__interna=True)

    assert entrar(cliente).get(f"/anexos/{interno.pk}").status_code == 404
    assert entrar(operador).get(f"/anexos/{interno.pk}").status_code == 200


def test_pagina_de_ocorrencia_de_outra_empresa_e_404(ocorrencia, estranho, entrar):
    assert entrar(estranho).get(f"/portal/{ocorrencia.pk}").status_code == 404


def test_colega_nao_envia_mensagem_pela_tela(ocorrencia, colega, entrar):
    antes = ocorrencia.mensagens.count()

    entrar(colega).post(f"/portal/{ocorrencia.pk}/mensagem", {"conteudo": "intruso"})

    assert ocorrencia.mensagens.count() == antes


def test_colega_nao_aprova_nem_reabre_pela_tela(ocorrencia, colega, operador, entrar):
    ocorrencia.status = "resolvida"
    ocorrencia.save(por=operador)
    http = entrar(colega)

    http.post(f"/portal/{ocorrencia.pk}/aprovar")
    http.post(f"/portal/{ocorrencia.pk}/reabrir")

    ocorrencia.refresh_from_db()
    assert ocorrencia.status == "resolvida"
