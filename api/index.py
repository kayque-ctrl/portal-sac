"""
Ponto de entrada da Vercel (função Python): expõe o WSGI do Django como `app`.
Todas as rotas são reescritas para cá em vercel.json.
"""

import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

from config.wsgi import application  # noqa: E402

app = application
