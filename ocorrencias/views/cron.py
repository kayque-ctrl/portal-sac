"""Tarefas agendadas chamadas pelo Vercel Cron (spec 015)."""

import hmac

from django.conf import settings
from django.http import Http404, JsonResponse
from django.views.decorators.http import require_GET

from .. import servicos

DIAS_PARA_ARQUIVAR = 30


def _autorizado(request) -> bool:
    """A Vercel envia `Authorization: Bearer <CRON_SECRET>`. Sem segredo configurado, a rota fica desligada."""
    segredo = settings.CRON_SECRET
    if not segredo:
        return False
    recebido = request.headers.get("Authorization", "")
    return hmac.compare_digest(recebido.encode(), f"Bearer {segredo}".encode())


@require_GET
def arquivar(request):
    """Antes: pg_cron. Arquiva as encerradas paradas há mais de 30 dias."""
    if not _autorizado(request):
        raise Http404
    return JsonResponse({"arquivadas": servicos.arquivar_concluidas_antigas(DIAS_PARA_ARQUIVAR)})
