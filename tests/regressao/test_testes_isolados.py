"""Protege: a suíte nunca usa o banco nem o storage do .env (ex.: Supabase de produção).

Em 2026-10-15, com DATABASE_URL do Supabase no .env, o pytest tentou criar o
banco de testes na produção (só não conseguiu por falta de permissão).
"""

from django.conf import settings


def test_suite_usa_settings_de_testes():
    import os

    assert os.environ["DJANGO_SETTINGS_MODULE"] == "config.settings_testes"
    assert settings.DATABASES["default"]["ENGINE"] == "django.db.backends.sqlite3" or os.environ.get(
        "TESTES_DATABASE_URL"
    )


def test_banco_dos_testes_nao_e_o_do_env(monkeypatch):
    import importlib

    import config.settings_testes as st

    monkeypatch.setenv("DATABASE_URL", "postgresql://django_app.ref:x@prod.pooler.supabase.com:6543/postgres")
    monkeypatch.delenv("TESTES_DATABASE_URL", raising=False)
    importlib.reload(st)

    assert st.DATABASES["default"]["ENGINE"] == "django.db.backends.sqlite3"


def test_storage_e_email_dos_testes_sao_locais():
    assert settings.ANEXOS_REMOTOS is False
    assert settings.STORAGES["default"]["BACKEND"] == "django.core.files.storage.FileSystemStorage"
    assert settings.SMTP_CONFIGURADO is False


def test_postgres_dos_testes_respeita_o_sslmode(monkeypatch):
    """O CI roda a suíte num Postgres sem SSL: TESTES_DATABASE_URL + DB_SSLMODE=disable."""
    import importlib

    import config.settings_testes as st

    monkeypatch.setenv("TESTES_DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/postgres")
    monkeypatch.setenv("DB_SSLMODE", "disable")
    importlib.reload(st)

    assert st.DATABASES["default"]["ENGINE"] == "django.db.backends.postgresql"
    assert st.DATABASES["default"]["OPTIONS"]["sslmode"] == "disable"
