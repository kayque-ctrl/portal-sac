"""Configuração por ambiente (config/ambiente.py), sem carregar outro settings."""

from pathlib import Path

import pytest
from django.core.exceptions import ImproperlyConfigured

from config import ambiente

BASE = Path("/projeto")
CHAVE_FORTE = "k" * 50
POOLER = "postgresql://django_app.ref:senha@aws-0-sa-east-1.pooler.supabase.com:6543/postgres"
DIRETA = "postgresql://django_app:senha@db.ref.supabase.co:5432/postgres"
S3 = {
    "STORAGE_BACKEND": "supabase",
    "SUPABASE_S3_ENDPOINT": "https://ref.supabase.co/storage/v1/s3",
    "SUPABASE_S3_BUCKET": "anexos-django",
    "SUPABASE_S3_KEY": "chave",
    "SUPABASE_S3_SECRET": "segredo",
    "SUPABASE_S3_REGION": "sa-east-1",
}


@pytest.mark.parametrize(("valor", "esperado"), [("true", True), ("1", True), (" ON ", True), ("false", False), ("", False), (None, False)])
def test_booleano(valor, esperado):
    assert ambiente.booleano(valor) is esperado


def test_booleano_usa_o_padrao_quando_ausente():
    assert ambiente.booleano(None, True) is True


def test_lista_ignora_vazios_e_espacos():
    assert ambiente.lista(" a.com, ,b.com ") == ["a.com", "b.com"]
    assert ambiente.lista(None) == []


# ---------------------------------------------------------------- banco


def test_sem_database_url_usa_sqlite_local():
    cfg = ambiente.banco({}, BASE)
    assert cfg == {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE / "db.sqlite3"}


def test_pooler_em_modo_transacao_desliga_prepared_statements_e_cursores():
    cfg = ambiente.banco({"DATABASE_URL": POOLER}, BASE)

    assert cfg["ENGINE"] == "django.db.backends.postgresql"
    assert (cfg["HOST"], cfg["PORT"], cfg["USER"]) == ("aws-0-sa-east-1.pooler.supabase.com", 6543, "django_app.ref")
    assert cfg["OPTIONS"]["prepare_threshold"] is None
    assert cfg["DISABLE_SERVER_SIDE_CURSORS"] is True
    assert cfg["CONN_MAX_AGE"] == 0


def test_conexao_direta_mantem_o_padrao_do_psycopg():
    cfg = ambiente.banco({"DATABASE_URL": DIRETA}, BASE)
    assert "prepare_threshold" not in cfg["OPTIONS"]
    assert not cfg.get("DISABLE_SERVER_SIDE_CURSORS")


def test_postgres_exige_ssl_por_padrao_e_aceita_desligar_localmente():
    assert ambiente.banco({"DATABASE_URL": DIRETA}, BASE)["OPTIONS"]["sslmode"] == "require"
    local = ambiente.banco({"DATABASE_URL": "postgresql://u:s@localhost:5432/db", "DB_SSLMODE": "disable"}, BASE)
    assert local["OPTIONS"]["sslmode"] == "disable"


# ---------------------------------------------------------------- arquivos


def test_anexos_locais_por_padrao():
    assert not ambiente.anexos_remotos({})
    assert ambiente.storages({})["default"] == {"BACKEND": "django.core.files.storage.FileSystemStorage"}


def test_anexos_no_bucket_privado_do_supabase_com_url_assinada_curta():
    cfg = ambiente.storages(S3)["default"]
    opcoes = cfg["OPTIONS"]

    assert ambiente.anexos_remotos(S3)
    assert cfg["BACKEND"] == "storages.backends.s3.S3Storage"
    assert opcoes["bucket_name"] == "anexos-django"
    assert opcoes["querystring_auth"] is True
    assert opcoes["querystring_expire"] == 60
    assert opcoes["default_acl"] is None
    assert opcoes["file_overwrite"] is False
    assert opcoes["addressing_style"] == "path"


@pytest.mark.parametrize("ausente", ambiente.VARIAVEIS_STORAGE)
def test_storage_do_supabase_exige_todas_as_variaveis(ausente):
    env = {k: v for k, v in S3.items() if k != ausente}
    with pytest.raises(ImproperlyConfigured, match=ausente):
        ambiente.storages(env)


def test_estaticos_nao_dependem_de_collectstatic():
    assert ambiente.storages({})["staticfiles"]["BACKEND"] == "django.contrib.staticfiles.storage.StaticFilesStorage"


# ---------------------------------------------------------------- segurança


def test_em_desenvolvimento_nada_muda():
    assert ambiente.seguranca({}, True, ambiente.SECRET_DEV, []) == {}


@pytest.mark.parametrize("chave", [ambiente.SECRET_DEV, "", "curta"])
def test_producao_recusa_chave_fraca_ou_de_desenvolvimento(chave):
    with pytest.raises(ImproperlyConfigured, match="DJANGO_SECRET_KEY"):
        ambiente.seguranca({}, False, chave, ["app.vercel.app"])


def test_producao_exige_hosts_permitidos():
    with pytest.raises(ImproperlyConfigured, match="DJANGO_ALLOWED_HOSTS"):
        ambiente.seguranca({}, False, CHAVE_FORTE, [])


def test_producao_liga_https_cookies_seguros_e_hsts():
    cfg = ambiente.seguranca({}, False, CHAVE_FORTE, ["app.vercel.app"])

    assert cfg["SECURE_PROXY_SSL_HEADER"] == ("HTTP_X_FORWARDED_PROTO", "https")
    assert cfg["SECURE_SSL_REDIRECT"] is True
    assert cfg["SESSION_COOKIE_SECURE"] and cfg["CSRF_COOKIE_SECURE"]
    assert cfg["SECURE_HSTS_SECONDS"] == 60 * 60 * 24 * 30


def test_producao_permite_ajustar_redirect_e_hsts():
    cfg = ambiente.seguranca({"DJANGO_SSL_REDIRECT": "false", "DJANGO_HSTS_SECONDS": "0"}, False, CHAVE_FORTE, ["x"])
    assert (cfg["SECURE_SSL_REDIRECT"], cfg["SECURE_HSTS_SECONDS"]) == (False, 0)


# ---------------------------------------------------------------- uploads


@pytest.mark.parametrize(("env", "esperado"), [({}, 50 * 1024 * 1024), ({"UPLOAD_MAX_TOTAL_MB": "4"}, 4 * 1024 * 1024), ({"UPLOAD_MAX_TOTAL_MB": "4.5"}, int(4.5 * 1024 * 1024))])
def test_limite_total_de_upload(env, esperado):
    assert ambiente.limite_total_upload(env) == esperado


@pytest.mark.parametrize("valor", ["0", "-1"])
def test_limite_total_de_upload_invalido(valor):
    with pytest.raises(ImproperlyConfigured):
        ambiente.limite_total_upload({"UPLOAD_MAX_TOTAL_MB": valor})


# ---------------------------------------------------------------- e-mail

SMTP = {"SMTP_HOST": "smtp.gmail.com", "SMTP_USER": "u@x.com", "SMTP_PASS": "senha", "EMAIL_FROM": "Portal <u@x.com>"}


def test_sem_smtp_os_emails_vao_para_o_console():
    cfg = ambiente.email({"SMTP_HOST": "smtp.gmail.com"})
    assert cfg == {"SMTP_CONFIGURADO": False, "EMAIL_BACKEND": "django.core.mail.backends.console.EmailBackend"}


@pytest.mark.parametrize(("porta", "ssl", "tls"), [("587", False, True), ("465", True, False)])
def test_smtp_escolhe_tls_ou_ssl_pela_porta(porta, ssl, tls):
    cfg = ambiente.email({**SMTP, "SMTP_PORT": porta})
    assert cfg["SMTP_CONFIGURADO"] is True
    assert cfg["EMAIL_BACKEND"] == "django.core.mail.backends.smtp.EmailBackend"
    assert (cfg["EMAIL_USE_SSL"], cfg["EMAIL_USE_TLS"]) == (ssl, tls)
    assert cfg["EMAIL_HOST_PASSWORD"] == "senha"
