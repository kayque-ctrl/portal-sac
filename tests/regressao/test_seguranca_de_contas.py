"""Protege: autenticação, convite e escalada de privilégio (specs 008 e 013)."""

import re

from django.core import mail

from contas.models import Usuario
from ocorrencias import servicos
from ocorrencias.models import Ocorrencia

from ..builders import dados_atraso

MENSAGEM_ADMIN = "Apenas um administrador pode conceder o papel de admin."


def _parametros(caminho: str) -> dict:
    return dict(p.split("=", 1) for p in caminho.split("?", 1)[1].split("&"))


def _link_do_convite(email) -> str:
    link = re.search(r'href="([^"]+/auth/confirm[^"]+)"', email.body).group(1).replace("&amp;", "&")
    return link.split("localhost:8000", 1)[1]


def test_operador_nao_cria_admin(operador, entrar):
    r = entrar(operador).post("/operacao/usuarios", {"nome": "X", "email": "x@x.com", "papel": "admin"})
    assert MENSAGEM_ADMIN in r.content.decode()
    assert not Usuario.objects.filter(email="x@x.com").exists()


def test_operador_nao_promove_usuario_a_admin(operador, cliente, entrar):
    r = entrar(operador).post(f"/operacao/usuarios/{cliente.pk}", {"nome": "Ana", "papel": "admin"})

    assert MENSAGEM_ADMIN in r.content.decode()
    cliente.refresh_from_db()
    assert cliente.papel == "cliente"


def test_convite_cria_sempre_cliente_sem_senha(operador, empresa, entrar):
    entrar(operador).post(
        "/operacao/usuarios",
        {"nome": "Nova Pessoa", "email": "nova@acme.com", "papel": "cliente", "empresa_id": str(empresa.pk)},
    )

    novo = Usuario.objects.get(email="nova@acme.com")
    assert novo.papel == "cliente"
    assert novo.ativado_em is None
    assert not novo.has_usable_password()


def test_link_de_convite_e_de_uso_unico(operador, empresa, client, entrar):
    entrar(operador).post(
        "/operacao/usuarios",
        {"nome": "Nova Pessoa", "email": "nova@acme.com", "papel": "cliente", "empresa_id": str(empresa.pk)},
    )
    caminho = _link_do_convite(mail.outbox[-1])
    client.logout()

    # GET só mostra o botão: não consome o token.
    assert "Confirmar acesso" in client.get(caminho).content.decode()
    r = client.post("/auth/confirm", _parametros(caminho))
    assert r.status_code == 302 and r.url == "/definir-senha"

    client.post("/definir-senha", {"senha": "nova-senha-123", "confirma": "nova-senha-123"})
    novo = Usuario.objects.get(email="nova@acme.com")
    assert novo.ativado_em is not None
    assert novo.check_password("nova-senha-123")

    client.logout()
    r = client.post("/auth/confirm", _parametros(caminho))
    assert r.url == "/login?erro=convite"


def test_esqueci_senha_nao_revela_se_o_email_existe(cliente, client):
    existente = client.post("/esqueci-senha", {"email": "cliente@acme.com"})
    inexistente = client.post("/esqueci-senha", {"email": "ninguem@acme.com"})

    assert "Se esse e-mail estiver cadastrado" in existente.content.decode()
    assert "Se esse e-mail estiver cadastrado" in inexistente.content.decode()
    assert len(mail.outbox) == 1


def test_login_aceita_email_em_maiusculas_e_recusa_senha_errada(cliente, client):
    r = client.post("/login", {"email": "cliente@acme.com", "password": "errada"})
    assert "E-mail ou senha inválidos." in r.content.decode()

    r = client.post("/login", {"email": "CLIENTE@acme.com", "password": "senha-forte-1"})
    assert r.url == "/apos-login"


def test_usuario_com_ocorrencias_nao_pode_ser_excluido(cliente, colega, operador, entrar):
    servicos.criar_ocorrencia(cliente, dados_atraso(), [])
    cliente_http = entrar(operador)

    cliente_http.post(f"/operacao/usuarios/{cliente.pk}/excluir")
    cliente_http.post(f"/operacao/usuarios/{colega.pk}/excluir")

    assert Usuario.objects.filter(pk=cliente.pk).exists()
    assert Ocorrencia.objects.filter(cliente=cliente).exists()
    assert not Usuario.objects.filter(pk=colega.pk).exists()
