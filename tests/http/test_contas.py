"""Login, logout, esqueci a senha, confirmação de link e definição de senha."""

import pytest
from django.core import mail

from contas import convites

from ..builders import SENHA


def corpo(resposta) -> str:
    return resposta.content.decode()


# ---------------------------------------------------------------- login


def test_login_ja_autenticado_vai_para_o_roteador(cliente, entrar):
    assert entrar(cliente).get("/login").url == "/apos-login"


def test_login_exige_email_e_senha(client, db):
    assert "Preencha e-mail e senha." in corpo(client.post("/login", {"email": "", "password": ""}))


def test_login_de_usuario_inativo_e_recusado(cliente, client):
    cliente.is_active = False
    cliente.save()
    r = client.post("/login", {"email": cliente.email, "password": SENHA})
    assert "E-mail ou senha inválidos." in corpo(r)


def test_login_mostra_erro_de_convite_invalido(client, db):
    assert "Link inválido ou expirado" in corpo(client.get("/login?erro=convite"))


def test_logout_encerra_a_sessao(cliente, entrar):
    http = entrar(cliente)
    assert http.post("/sair").url == "/login"
    assert http.get("/portal/").url.startswith("/login")


def test_logout_so_aceita_post(cliente, entrar):
    assert entrar(cliente).get("/sair").status_code == 405


def test_apos_login_exige_estar_logado(client, db):
    assert client.get("/apos-login").url.startswith("/login")


# ---------------------------------------------------------------- esqueci a senha


@pytest.mark.parametrize("email", ["", "sem-arroba"])
def test_esqueci_senha_valida_o_formato(client, db, email):
    assert "Informe um e-mail válido." in corpo(client.post("/esqueci-senha", {"email": email}))
    assert mail.outbox == []


def test_esqueci_senha_nao_envia_para_usuario_inativo(cliente, client):
    cliente.is_active = False
    cliente.save()
    client.post("/esqueci-senha", {"email": cliente.email})
    assert mail.outbox == []


# ---------------------------------------------------------------- confirmação do link


def link_para(user):
    gerado = convites.gerar_link(user)
    return gerado.split("localhost:8000", 1)[1]


def test_confirmar_sem_parametros_volta_ao_login(client, db):
    assert client.get("/auth/confirm").url == "/login?erro=convite"


def test_token_invalido_nao_autentica(cliente, client):
    uid = link_para(cliente).split("uid=")[1].split("&")[0]
    r = client.post("/auth/confirm", {"uid": uid, "token": "token-errado"})
    assert r.url == "/login?erro=convite"
    assert "_auth_user_id" not in client.session


def test_usuario_inativo_nao_usa_o_link(cliente, client):
    caminho = link_para(cliente)
    cliente.is_active = False
    cliente.save()
    uid, token = (p.split("=")[1] for p in caminho.split("?")[1].split("&")[:2])
    assert client.post("/auth/confirm", {"uid": uid, "token": token}).url == "/login?erro=convite"


@pytest.mark.parametrize("destino", ["https://malicioso.com", "//malicioso.com", "javascript:alert(1)"])
def test_confirmacao_nao_redireciona_para_fora_do_site(cliente, client, destino):
    """Open redirect: o parâmetro next só pode apontar para o próprio site."""
    uid, token = (p.split("=")[1] for p in link_para(cliente).split("?")[1].split("&")[:2])

    r = client.post("/auth/confirm", {"uid": uid, "token": token, "next": destino})

    assert r.url == "/"


def test_confirmacao_respeita_destino_interno(cliente, client):
    uid, token = (p.split("=")[1] for p in link_para(cliente).split("?")[1].split("&")[:2])
    r = client.post("/auth/confirm", {"uid": uid, "token": token, "next": "/definir-senha"})
    assert r.url == "/definir-senha"


# ---------------------------------------------------------------- definir senha


@pytest.mark.parametrize(
    ("senha", "confirma", "erro"),
    [
        ("curta", "curta", "A senha precisa ter ao menos 8 caracteres."),
        ("senha-longa-1", "outra-senha-1", "As senhas não conferem."),
    ],
)
def test_definir_senha_valida(cliente, entrar, senha, confirma, erro):
    r = entrar(cliente).post("/definir-senha", {"senha": senha, "confirma": confirma})
    assert erro in corpo(r)
    cliente.refresh_from_db()
    assert cliente.check_password(SENHA)


def test_definir_senha_sem_sessao_pede_novo_convite(client, db):
    r = client.post("/definir-senha", {"senha": "senha-longa-1", "confirma": "senha-longa-1"})
    assert "Link inválido ou expirado" in corpo(r)


def test_definir_senha_mantem_o_usuario_logado_e_nao_reativa(cliente, entrar):
    from django.utils import timezone

    ativado = timezone.now()
    cliente.ativado_em = ativado
    cliente.save()
    http = entrar(cliente)

    r = http.post("/definir-senha", {"senha": "nova-senha-123", "confirma": "nova-senha-123"})

    assert r.url == "/apos-login"
    cliente.refresh_from_db()
    assert cliente.ativado_em == ativado
    assert http.get("/portal/").status_code == 200


# ---------------------------------------------------------------- e-mails de acesso


def test_reenvio_e_redefinicao_enviam_email_com_link(cliente, settings):
    settings.SMTP_CONFIGURADO = True

    assert convites.reenviar_convite(cliente)
    assert convites.enviar_redefinicao(cliente)

    assert len(mail.outbox) == 2
    assert all("/auth/confirm?uid=" in m.body for m in mail.outbox)
