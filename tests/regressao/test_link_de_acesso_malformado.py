"""Protege: bug encontrado na cobertura de 2026-10-15 (link de acesso malformado).

Um `uid` que decodifica para algo que não é UUID fazia `usuario_do_token`
levantar ValidationError, e POST /auth/confirm respondia 500 numa rota pública.
O esperado é tratar como link inválido.
"""

import pytest

from contas import convites


@pytest.mark.parametrize("uid", ["%%%", "", "bm9wZQ", "MTIz"])  # lixo, vazio, "nope", "123"
def test_uid_malformado_e_tratado_como_link_invalido(db, uid):
    assert convites.usuario_do_token(uid, "qualquer") is None


def test_confirmacao_com_uid_malformado_volta_ao_login_sem_erro_500(client, db):
    r = client.post("/auth/confirm", {"uid": "bm9wZQ", "token": "x"})
    assert r.status_code == 302
    assert r.url == "/login?erro=convite"
