"""
Configurações do Portal de Ocorrências (Django).

Tudo que muda por ambiente vem de variáveis de ambiente (arquivo .env na raiz,
ver .env.example). Sem .env, roda em modo desenvolvimento com SQLite.
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _bool(nome: str, padrao: bool = False) -> bool:
    return os.environ.get(nome, str(padrao)).strip().lower() in ("1", "true", "yes", "on")


SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY", "dev-inseguro-troque-em-producao-0123456789abcdef"
)
DEBUG = _bool("DJANGO_DEBUG", True)
ALLOWED_HOSTS = [
    h.strip() for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if h.strip()
]
CSRF_TRUSTED_ORIGINS = [
    o.strip() for o in os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",") if o.strip()
]

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
# Padrão: SQLite. Para PostgreSQL defina DB_ENGINE=postgresql e as DB_* abaixo
# (requer `pip install psycopg[binary]`).
if os.environ.get("DB_ENGINE", "").lower() == "postgresql":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ.get("DB_NAME", "ocorrencias"),
            "USER": os.environ.get("DB_USER", "postgres"),
            "PASSWORD": os.environ.get("DB_PASSWORD", ""),
            "HOST": os.environ.get("DB_HOST", "localhost"),
            "PORT": os.environ.get("DB_PORT", "5432"),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

# ---------- Autenticação ----------
AUTH_USER_MODEL = "contas.Usuario"
LOGIN_URL = "contas:login"
LOGIN_REDIRECT_URL = "contas:apos_login"
LOGOUT_REDIRECT_URL = "contas:login"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
]

# Testes: hash rápido (o padrão PBKDF2 deixa a suíte lenta).
if "test" in sys.argv:
    PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

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

# Anexos ficam em MEDIA_ROOT, mas NUNCA são servidos direto: o download passa
# por uma view que confere se o usuário pode ver a ocorrência (substitui o
# bucket privado + URLs assinadas do Supabase Storage).
MEDIA_ROOT = BASE_DIR / "media"

DATA_UPLOAD_MAX_MEMORY_SIZE = 60 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------- E-mail ----------
# Envio é best-effort: sem SMTP_HOST/SMTP_USER/SMTP_PASS/EMAIL_FROM o app
# funciona normalmente, só não envia (o conteúdo é logado no console).
SMTP_CONFIGURADO = all(os.environ.get(k) for k in ("SMTP_HOST", "SMTP_USER", "SMTP_PASS", "EMAIL_FROM"))
if SMTP_CONFIGURADO:
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    EMAIL_HOST = os.environ["SMTP_HOST"]
    EMAIL_PORT = int(os.environ.get("SMTP_PORT", "587"))
    EMAIL_HOST_USER = os.environ["SMTP_USER"]
    EMAIL_HOST_PASSWORD = os.environ["SMTP_PASS"]
    EMAIL_USE_SSL = EMAIL_PORT == 465
    EMAIL_USE_TLS = EMAIL_PORT != 465
    EMAIL_TIMEOUT = 15
else:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
DEFAULT_FROM_EMAIL = os.environ.get("EMAIL_FROM", "Portal de Ocorrências <nao-responda@localhost>")

# URL base usada nos links dos e-mails.
SITE_URL = os.environ.get("SITE_URL", "http://localhost:8000").rstrip("/")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "loggers": {
        "ocorrencias": {"handlers": ["console"], "level": "INFO"},
        "contas": {"handlers": ["console"], "level": "INFO"},
    },
}
