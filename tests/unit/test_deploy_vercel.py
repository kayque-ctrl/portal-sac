"""Arquivos de deploy (spec 015): coerência entre vercel.json, rotas e entrada WSGI."""

import json
from pathlib import Path

from django.urls import resolve

RAIZ = Path(__file__).resolve().parents[2]


def vercel() -> dict:
    return json.loads((RAIZ / "vercel.json").read_text(encoding="utf-8"))


def test_todas_as_rotas_vao_para_o_django():
    assert vercel()["rewrites"] == [{"source": "/(.*)", "destination": "/api/index"}]
    assert "api/index.py" in vercel()["functions"]


def test_cron_aponta_para_uma_rota_existente():
    crons = vercel()["crons"]
    assert crons == [{"path": "/cron/arquivar", "schedule": "0 6 * * *"}]  # 03:00 em Brasília
    assert resolve(crons[0]["path"]).url_name == "cron_arquivar"


def test_entrada_da_vercel_expoe_o_wsgi_do_django():
    from django.core.handlers.wsgi import WSGIHandler

    from api.index import app

    assert isinstance(app, WSGIHandler)


def test_vercelignore_nao_publica_segredos_nem_dados_locais():
    ignorados = (RAIZ / ".vercelignore").read_text(encoding="utf-8").split()
    for item in (".env", "db.sqlite3", "media/", ".venv/"):
        assert item in ignorados


def test_dependencias_de_producao_estao_no_requirements():
    reqs = (RAIZ / "requirements.txt").read_text(encoding="utf-8")
    for pacote in ("psycopg[binary]", "dj-database-url", "django-storages[s3]", "whitenoise"):
        assert pacote in reqs


def test_script_do_supabase_cria_schema_privado_e_bucket_privado():
    sql = (RAIZ / "deploy" / "supabase.sql").read_text(encoding="utf-8")
    assert "create schema if not exists django authorization django_app" in sql
    assert "alter role django_app set search_path = django" in sql
    assert "revoke all on schema django from public, anon, authenticated" in sql
    assert "values ('anexos-django', 'anexos-django', false)" in sql


def test_entrada_da_vercel_poe_a_raiz_do_projeto_no_path(monkeypatch):
    """Na Vercel, a função roda a partir de api/: a raiz precisa entrar no sys.path."""
    import importlib
    import sys

    import api.index

    raiz = str(RAIZ)
    monkeypatch.setattr(sys, "path", [p for p in sys.path if p != raiz])
    importlib.reload(api.index)
    assert raiz in sys.path
