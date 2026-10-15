"""
Settings da suíte de testes (pytest.ini aponta para cá).

Os testes NUNCA usam o banco nem o storage do .env: com DATABASE_URL apontando
para o Supabase, o pytest tentaria usar a produção. Aqui o banco é SQLite, a
não ser que TESTES_DATABASE_URL seja definida de propósito (o CI a usa para
rodar a suíte num Postgres descartável).
"""

import os

from . import ambiente
from .settings import *  # noqa: F403
from .settings import BASE_DIR

DATABASES = {
    "default": ambiente.banco(
        {
            "DATABASE_URL": os.environ.get("TESTES_DATABASE_URL", ""),
            # O Postgres descartável do CI não tem SSL (DB_SSLMODE=disable no workflow).
            "DB_SSLMODE": os.environ.get("DB_SSLMODE", "require"),
        },
        BASE_DIR,
    )
}

STORAGES = ambiente.storages({})
ANEXOS_REMOTOS = False
UPLOAD_MAX_TOTAL_BYTES = ambiente.limite_total_upload({})
CRON_SECRET = ""
SMTP_CONFIGURADO = False
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
SITE_URL = "http://localhost:8000"
