"""Fixtures compartilhadas e convenções da suíte (ver docs/05-testes.md).

Marcadores por pasta: tudo em `tests/unit` recebe `unit`, `tests/regras`
recebe `regras`, e assim por diante, sem precisar decorar cada teste.
"""

from pathlib import Path

import pytest

from contas.models import Empresa, Papel, Usuario
from ocorrencias import servicos

from .builders import SENHA, dados_atraso, dados_produtos, foto

PASTAS_MARCADORES = {"unit", "regras", "http", "regressao"}


def pytest_collection_modifyitems(items):
    for item in items:
        pasta = Path(item.fspath).parent.name
        if pasta in PASTAS_MARCADORES:
            item.add_marker(getattr(pytest.mark, pasta))


# ---------------------------------------------------------------- ambiente


@pytest.fixture(autouse=True)
def _arquivos_em_pasta_temporaria(settings, tmp_path):
    """Anexos nunca vão para o media/ real."""
    settings.MEDIA_ROOT = tmp_path / "media"


@pytest.fixture(autouse=True)
def _senha_rapida(settings):
    """Hash barato: criar usuários não pode pesar na suíte."""
    settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]


# ---------------------------------------------------------------- elenco
# Elenco padrão: ACME (cliente + colega), Globex (estranho), operador e admin.


def _usuario(email, nome, **kw):
    return Usuario.objects.create_user(email, SENHA, nome=nome, **kw)


@pytest.fixture
def empresa(db):
    return Empresa.objects.create(nome="ACME")


@pytest.fixture
def outra_empresa(db):
    return Empresa.objects.create(nome="Globex")


@pytest.fixture
def cliente(empresa):
    return _usuario("cliente@acme.com", "Ana Cliente", empresa=empresa, documento="123.456.789-00")


@pytest.fixture
def colega(empresa):
    """Outro usuário da mesma empresa do `cliente`: lê, mas não age."""
    return _usuario("colega@acme.com", "Bruno Colega", empresa=empresa)


@pytest.fixture
def estranho(outra_empresa):
    """Usuário de outra empresa: não pode ver nada da ACME."""
    return _usuario("x@globex.com", "Carla Globex", empresa=outra_empresa)


@pytest.fixture
def sem_empresa(db):
    return _usuario("solo@x.com", "Solo")


@pytest.fixture
def operador(db):
    return _usuario("op@empresa.com", "Otto Operador", papel=Papel.OPERADOR)


@pytest.fixture
def admin(db):
    return _usuario("admin@empresa.com", "Alice Admin", papel=Papel.ADMIN)


# ---------------------------------------------------------------- ações


@pytest.fixture
def abrir(cliente):
    """Abre uma ocorrência de atraso pelo serviço (padrão: como `cliente`)."""

    def _abrir(por=None, **extra):
        r = servicos.criar_ocorrencia(por or cliente, dados_atraso(**extra), [])
        assert r.ok, r.erro
        return r.dados["ocorrencia"]

    return _abrir


@pytest.fixture
def responder(operador):
    """A operação responde ao cliente (move aberta → em tratativa)."""

    def _responder(oc, por=None):
        r = servicos.adicionar_mensagem(por or operador, oc, "Estamos verificando.", False, [])
        assert r.ok, r.erro
        oc.refresh_from_db()
        return oc

    return _responder


@pytest.fixture
def entrar(client):
    """Autentica o `client` como o usuário informado: `entrar(operador)`."""

    def _entrar(user):
        client.force_login(user)
        return client

    return _entrar


@pytest.fixture
def ocorrencia(cliente, operador):
    """Ocorrência de avaria da `cliente`, com foto e uma resposta pública da operação (com anexo)."""
    r = servicos.criar_ocorrencia(cliente, dados_produtos("avaria"), [foto()])
    assert r.ok, r.erro
    oc = r.dados["ocorrencia"]
    servicos.adicionar_mensagem(operador, oc, "Olá, vamos verificar.", False, [foto("resp.png")])
    oc.refresh_from_db()
    return oc
