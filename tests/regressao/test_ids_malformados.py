"""Protege: ids vindos de formulário que não são UUID nunca podem gerar erro 500.

Mesma classe do bug do link de acesso malformado (test_link_de_acesso_malformado.py):
`filter(pk="lixo")` num UUIDField levanta ValidationError. Todo id de formulário
passa por `uuids_validos` ou é tratado como inválido.
"""

import pytest

from ocorrencias import servicos


@pytest.mark.parametrize("valor", ["lixo", "123", "' OR 1=1 --"])
def test_responsavel_malformado_e_recusado_sem_erro(abrir, operador, valor):
    r = servicos.atualizar_ocorrencia(
        operador, abrir(), {"status": "aberta", "prioridade": "media", "atribuido_a": valor}
    )
    assert r.erro == "Responsável inválido."


def test_responsavel_malformado_pela_tela_mostra_o_erro(ocorrencia, operador, entrar):
    r = entrar(operador).post(
        f"/operacao/{ocorrencia.pk}/atualizar", {"status": "em_analise", "prioridade": "media", "atribuido_a": "lixo"}
    )
    assert r.status_code == 200
    assert "Responsável inválido." in r.content.decode()


@pytest.mark.parametrize(
    "rota",
    [
        "/operacao/?empresa=lixo",
        "/operacao/painel?empresa=lixo",
        "/operacao/painel/export?empresa=lixo",
        "/operacao/usuarios?empresa=lixo",
    ],
)
def test_filtros_com_id_malformado_nao_quebram(admin, entrar, rota):
    assert entrar(admin).get(rota).status_code == 200


@pytest.mark.parametrize(
    ("rota", "dados"),
    [
        ("/operacao/lixeira/excluir", {"ids": ["lixo"]}),
        ("/notificacoes/marcar-lidas", {"ids": ["lixo"]}),
        ("/operacao/usuarios", {"nome": "Fulano", "email": "f@x.com", "empresa_id": "lixo"}),
    ],
)
def test_posts_com_id_malformado_nao_quebram(admin, entrar, rota, dados):
    assert entrar(admin).post(rota, dados).status_code in (200, 302)


def test_vinculo_de_empresa_com_id_malformado_nao_quebra(empresa, admin, entrar):
    assert entrar(admin).post(f"/operacao/empresas/{empresa.pk}", {"userId": "lixo"}).status_code == 302
