"""
System checks do projeto.

ocorrencias.E001: no Postgres do Supabase o schema `public` é exposto pela API
do Supabase. As tabelas do Django ficam no schema `django` (spec 015); se a
conexão cair em outro schema, o migrate criaria tabelas expostas. O check roda
antes do migrate e o bloqueia.
"""

from django.conf import settings
from django.core.checks import Error, Tags, register
from django.db import connections


@register(Tags.database)
def schema_do_banco(app_configs, databases=None, **kwargs):
    erros = []
    for alias in databases or []:
        conexao = connections[alias]
        if conexao.vendor != "postgresql":
            continue
        with conexao.cursor() as cursor:
            cursor.execute("select current_schema()")
            atual = cursor.fetchone()[0]
        if atual != settings.DB_SCHEMA:
            erros.append(
                Error(
                    f"A conexão '{alias}' está no schema {atual!r}, mas o esperado é {settings.DB_SCHEMA!r}.",
                    hint=(
                        "Conecte com o usuário django_app, cujo search_path é o schema django "
                        "(ver deploy/supabase.sql), ou ajuste DB_SCHEMA."
                    ),
                    id="ocorrencias.E001",
                )
            )
    return erros
