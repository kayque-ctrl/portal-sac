"""Protege: spec 007 (nenhuma ação falha sem mostrar o motivo) e uploads."""

from django.core.files.uploadedfile import SimpleUploadedFile

from ocorrencias import servicos

from ..builders import dados_atraso


def test_erro_ao_mudar_status_aparece_na_tela(ocorrencia, operador, entrar):
    r = entrar(operador).post(
        f"/operacao/{ocorrencia.pk}/atualizar", {"status": "resolvida", "prioridade": "media", "atribuido_a": ""}
    )
    assert "Não é possível mudar o status: falta um responsável definido." in r.content.decode()


def test_erro_ao_enviar_mensagem_vazia_aparece_na_tela(ocorrencia, cliente, entrar):
    r = entrar(cliente).post(f"/portal/{ocorrencia.pk}/mensagem", {"conteudo": ""})
    assert "Escreva uma mensagem ou anexe um arquivo." in r.content.decode()


def test_erro_de_abertura_volta_ao_formulario_com_o_que_foi_preenchido(cliente, entrar):
    r = entrar(cliente).post("/portal/nova", dados_atraso(descricao="curta"))

    corpo = r.content.decode()
    assert "Descreva a ocorrência com pelo menos 10 caracteres." in corpo
    assert '"referencia": "987"' in corpo


def test_aprovar_apos_mudanca_de_estado_mostra_erro_em_vez_de_aprovada(ocorrencia, cliente, entrar):
    """A ocorrência não está 'resolvida': a tela não pode dizer que aprovou."""
    r = entrar(cliente).post(f"/portal/{ocorrencia.pk}/aprovar", follow=True)

    corpo = r.content.decode()
    assert "Não foi possível aprovar" in corpo
    assert "Ocorrência aprovada!" not in corpo


def test_imagem_falsa_e_recusada(cliente):
    falsa = SimpleUploadedFile("x.png", b"isto nao e imagem", content_type="image/png")
    r = servicos.criar_ocorrencia(cliente, dados_atraso(), [falsa])
    assert r.erro == '"x.png" não parece uma imagem válida.'
