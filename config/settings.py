"""
Configurações do Portal de Ocorrências (Django).

Tudo que muda por ambiente vem de variáveis de ambiente (arquivo .env na raiz,
ver .env.example). Sem .env, roda em modo desenvolvimento com SQLite.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

from . import ambiente

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")
ENV = os.environ

SECRET_KEY = ENV.get("DJANGO_SECRET_KEY", ambiente.SECRET_DEV)
DEBUG = ambiente.debug(ENV)
ALLOWED_HOSTS = ambiente.lista(ENV.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1"))
CSRF_TRUSTED_ORIGINS = ambiente.lista(ENV.get("DJANGO_CSRF_TRUSTED_ORIGINS"))

# Produção: HTTPS, cookies seguros, HSTS; recusa subir com chave de desenvolvimento.
globals().update(ambiente.seguranca(ENV, DEBUG, SECRET_KEY, ALLOWED_HOSTS))

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "contas",
    "ocorrencias",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    *([] if DEBUG else ["whitenoise.middleware.WhiteNoiseMiddleware"]),
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "ocorrencias.context_processors.cabecalho",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# ---------- Banco ----------
# DATABASE_URL (Postgres do Supabase, schema `django`) ou SQLite local sem ela.
DATABASES = {"default": ambiente.banco(ENV, BASE_DIR)}
# Schema esperado no Postgres; conferido pelo check `ocorrencias.E001` antes do migrate.
DB_SCHEMA = ENV.get("DB_SCHEMA", "django")

# ---------- Autenticação ----------
AUTH_USER_MODEL = "contas.Usuario"
LOGIN_URL = "contas:login"
LOGIN_REDIRECT_URL = "contas:apos_login"
LOGOUT_REDIRECT_URL = "contas:login"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
]

# Validade do link de convite / redefinição de senha (segundos).
PASSWORD_RESET_TIMEOUT = 60 * 60 * 24 * 3

# ---------- Localização ----------
LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True

# ---------- Arquivos ----------
STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
# Produção: o WhiteNoise serve static/ e o admin direto das pastas, sem
# collectstatic. Sem hash no nome, então o cache do navegador é curto (1 h).
WHITENOISE_USE_FINDERS = True
WHITENOISE_MAX_AGE = 60 * 60

# Anexos: MEDIA_ROOT em desenvolvimento ou bucket privado do Supabase em
# produção (STORAGE_BACKEND=supabase). Nunca são servidos direto: o download
# passa pela view /anexos/<id>, que confere se o usuário pode ver a ocorrência.
MEDIA_ROOT = BASE_DIR / "media"
STORAGES = ambiente.storages(ENV)
ANEXOS_REMOTOS = ambiente.anexos_remotos(ENV)

# Soma máxima dos anexos de um envio (na Vercel, UPLOAD_MAX_TOTAL_MB=4).
UPLOAD_MAX_TOTAL_BYTES = ambiente.limite_total_upload(ENV)

DATA_UPLOAD_MAX_MEMORY_SIZE = 60 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------- E-mail ----------
# Envio é best-effort: sem SMTP_HOST/SMTP_USER/SMTP_PASS/EMAIL_FROM o app
# funciona normalmente, só não envia (o conteúdo é logado no console).
globals().update(ambiente.email(ENV))
DEFAULT_FROM_EMAIL = os.environ.get("EMAIL_FROM", "Portal de Ocorrências <nao-responda@localhost>")

# URL base usada nos links dos e-mails.
SITE_URL = os.environ.get("SITE_URL", "http://localhost:8000").rstrip("/")

# Segredo do Vercel Cron (cabeçalho Authorization: Bearer <CRON_SECRET>).
# Vazio desliga a rota /cron/arquivar.
CRON_SECRET = ENV.get("CRON_SECRET", "")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "loggers": {
        "ocorrencias": {"handlers": ["console"], "level": "INFO"},
        "contas": {"handlers": ["console"], "level": "INFO"},
        # Em produção o Django silencia estes por padrão; no console eles aparecem
        # nos Runtime Logs da Vercel (ex.: motivo de um 400 DisallowedHost ou de um 500).
        "django.security": {"handlers": ["console"], "level": "WARNING", "propagate": False},
        "django.request": {"handlers": ["console"], "level": "WARNING", "propagate": False},
    },
}
