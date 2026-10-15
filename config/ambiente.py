"""
Configuração que muda por ambiente, em funções puras sobre as variáveis de
ambiente (um dict). O settings.py só chama estas funções; assim cada regra de
produção pode ser testada sem recarregar o Django (tests/unit/test_ambiente.py).

Produção (spec 015): Vercel + Supabase. Banco no schema `django` (fora do
`public`, que a API do Supabase expõe), anexos num bucket privado do Storage.
"""

from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured

SECRET_DEV = "dev-inseguro-troque-em-producao-0123456789abcdef"

# Porta do pooler do Supabase em modo transação (Supavisor).
PORTA_POOLER_TRANSACAO = 6543

VARIAVEIS_STORAGE = (
    "SUPABASE_S3_ENDPOINT",
    "SUPABASE_S3_BUCKET",
    "SUPABASE_S3_KEY",
    "SUPABASE_S3_SECRET",
    "SUPABASE_S3_REGION",
)


def booleano(valor: str | None, padrao: bool = False) -> bool:
    if valor is None:
        return padrao
    return valor.strip().lower() in ("1", "true", "yes", "on")


def debug(env: dict) -> bool:
    """
    DJANGO_DEBUG explícito manda. Sem ele, liga só fora da Vercel: em produção,
    esquecer a variável nunca pode ligar o modo debug (a Vercel define VERCEL=1).
    """
    return booleano(env.get("DJANGO_DEBUG"), not env.get("VERCEL"))


def lista(valor: str | None) -> list[str]:
    return [v.strip() for v in (valor or "").split(",") if v.strip()]


# ---------------------------------------------------------------- banco


def banco(env: dict, base_dir: Path) -> dict:
    """
    DATABASE_URL (Postgres do Supabase) ou, sem ela, SQLite local.

    Pelo pooler em modo transação (porta 6543) a conexão muda a cada
    transação: sem prepared statements (psycopg 3 os cria sozinho) e sem
    cursores no servidor, senão o Postgres acusa erro no meio das requisições.
    """
    url = env.get("DATABASE_URL")
    if not url:
        return {"ENGINE": "django.db.backends.sqlite3", "NAME": base_dir / "db.sqlite3"}

    cfg = dj_database_url.parse(url, conn_max_age=0)
    if "postgresql" in cfg["ENGINE"]:
        cfg.setdefault("OPTIONS", {})["sslmode"] = env.get("DB_SSLMODE", "require")
        if int(cfg.get("PORT") or 0) == PORTA_POOLER_TRANSACAO:
            cfg["OPTIONS"]["prepare_threshold"] = None
            cfg["DISABLE_SERVER_SIDE_CURSORS"] = True
    return cfg


# ---------------------------------------------------------------- arquivos


def anexos_remotos(env: dict) -> bool:
    return env.get("STORAGE_BACKEND", "local").strip().lower() == "supabase"


def storages(env: dict) -> dict:
    """
    Anexos: disco local (dev/testes) ou bucket PRIVADO do Supabase Storage via
    API S3. As URLs são assinadas e valem 60 s; quem decide se o usuário pode
    baixar continua sendo a view /anexos/<id>.
    """
    if anexos_remotos(env):
        faltando = [v for v in VARIAVEIS_STORAGE if not env.get(v)]
        if faltando:
            raise ImproperlyConfigured(f"STORAGE_BACKEND=supabase exige: {', '.join(faltando)}")
        default = {
            "BACKEND": "storages.backends.s3.S3Storage",
            "OPTIONS": {
                "endpoint_url": env["SUPABASE_S3_ENDPOINT"],
                "bucket_name": env["SUPABASE_S3_BUCKET"],
                "access_key": env["SUPABASE_S3_KEY"],
                "secret_key": env["SUPABASE_S3_SECRET"],
                "region_name": env["SUPABASE_S3_REGION"],
                "addressing_style": "path",
                "signature_version": "s3v4",
                "default_acl": None,
                "querystring_auth": True,
                "querystring_expire": 60,
                "file_overwrite": False,
            },
        }
    else:
        default = {"BACKEND": "django.core.files.storage.FileSystemStorage"}

    # Estáticos: em produção o WhiteNoise serve direto das pastas (USE_FINDERS),
    # sem depender de collectstatic no build da Vercel.
    return {"default": default, "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}}


# ---------------------------------------------------------------- segurança


def seguranca(env: dict, debug: bool, secret_key: str, allowed_hosts: list[str]) -> dict:
    """
    Em produção (DEBUG desligado) recusa subir com a chave de desenvolvimento
    ou sem hosts permitidos, e liga HTTPS, cookies seguros e HSTS.
    """
    if debug:
        return {}
    if not secret_key or secret_key == SECRET_DEV or len(secret_key) < 40:
        raise ImproperlyConfigured("Defina DJANGO_SECRET_KEY (40+ caracteres) em produção.")
    if not allowed_hosts:
        raise ImproperlyConfigured("Defina DJANGO_ALLOWED_HOSTS em produção.")
    return {
        # A Vercel termina o HTTPS e repassa o protocolo neste cabeçalho.
        "SECURE_PROXY_SSL_HEADER": ("HTTP_X_FORWARDED_PROTO", "https"),
        "SECURE_SSL_REDIRECT": booleano(env.get("DJANGO_SSL_REDIRECT"), True),
        "SESSION_COOKIE_SECURE": True,
        "CSRF_COOKIE_SECURE": True,
        "SECURE_HSTS_SECONDS": int(env.get("DJANGO_HSTS_SECONDS", 60 * 60 * 24 * 30)),
        "SECURE_HSTS_INCLUDE_SUBDOMAINS": False,
        "SECURE_CONTENT_TYPE_NOSNIFF": True,
        "SECURE_REFERRER_POLICY": "same-origin",
    }


# ---------------------------------------------------------------- e-mail


def email(env: dict) -> dict:
    """SMTP quando as 4 variáveis existem; senão, e-mails no console (best-effort)."""
    configurado = all(env.get(k) for k in ("SMTP_HOST", "SMTP_USER", "SMTP_PASS", "EMAIL_FROM"))
    if not configurado:
        return {"SMTP_CONFIGURADO": False, "EMAIL_BACKEND": "django.core.mail.backends.console.EmailBackend"}
    porta = int(env.get("SMTP_PORT", "587"))
    return {
        "SMTP_CONFIGURADO": True,
        "EMAIL_BACKEND": "django.core.mail.backends.smtp.EmailBackend",
        "EMAIL_HOST": env["SMTP_HOST"],
        "EMAIL_PORT": porta,
        "EMAIL_HOST_USER": env["SMTP_USER"],
        "EMAIL_HOST_PASSWORD": env["SMTP_PASS"],
        "EMAIL_USE_SSL": porta == 465,
        "EMAIL_USE_TLS": porta != 465,
        "EMAIL_TIMEOUT": 15,
    }


# ---------------------------------------------------------------- uploads


def limite_total_upload(env: dict) -> int:
    """
    Soma máxima dos anexos de um envio, em bytes. Na Vercel o corpo da
    requisição é limitado a 4,5 MB, então em produção use UPLOAD_MAX_TOTAL_MB=4
    (as fotos são comprimidas no navegador antes do envio).
    """
    mb = float(env.get("UPLOAD_MAX_TOTAL_MB", 50))
    if mb <= 0:
        raise ImproperlyConfigured("UPLOAD_MAX_TOTAL_MB precisa ser maior que zero.")
    return int(mb * 1024 * 1024)
