"""Decorators de acesso por papel e views compartilhadas (anexos, notificações)."""

import uuid
from functools import wraps

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from ..formato import tempo_relativo
from ..models import Anexo
from ..notificacoes import icone
from ..permissoes import pode_ver


def uuids_validos(valores) -> list[str]:
    saida = []
    for v in valores:
        try:
            saida.append(str(uuid.UUID(str(v))))
        except ValueError:
            continue
    return saida


def cliente_required(view):
    """Área do CLIENTE. Operação é mandada para /operacao."""

    @login_required
    @wraps(view)
    def inner(request, *args, **kwargs):
        if not request.user.eh_cliente:
            return redirect("operacao:lista")
        return view(request, *args, **kwargs)

    return inner


def operacao_required(view):
    """Área da OPERAÇÃO (operador ou admin). Cliente é mandado para /portal."""

    @login_required
    @wraps(view)
    def inner(request, *args, **kwargs):
        if not request.user.eh_operacao:
            return redirect("portal:inicio")
        return view(request, *args, **kwargs)

    return inner


def admin_required(view):
    @operacao_required
    @wraps(view)
    def inner(request, *args, **kwargs):
        if not request.user.eh_admin:
            return redirect("operacao:lista")
        return view(request, *args, **kwargs)

    return inner


@login_required
def baixar_anexo(request, pk):
    """Serve o arquivo só para quem pode ver a ocorrência (e nota interna só p/ operação)."""
    anexo = get_object_or_404(Anexo.objects.select_related("ocorrencia__cliente", "mensagem"), pk=pk)
    if not pode_ver(request.user, anexo.ocorrencia):
        raise Http404
    if anexo.mensagem and anexo.mensagem.interna and not request.user.eh_operacao:
        raise Http404
    if settings.ANEXOS_REMOTOS:
        # Bucket privado do Supabase: URL assinada que expira em 60 s. A
        # permissão já foi conferida acima; o link nunca aparece na página.
        return redirect(anexo.arquivo.url)
    try:
        arquivo = anexo.arquivo.open("rb")
    except FileNotFoundError:
        raise Http404 from None
    inline = (anexo.tipo_mime or "").startswith("image/") or anexo.tipo_mime == "application/pdf"
    return FileResponse(arquivo, as_attachment=not inline, filename=anexo.nome_arquivo, content_type=anexo.tipo_mime)


@login_required
def notificacoes_recentes(request):
    """Usado pelo sino do cabeçalho (polling a cada 30s)."""
    user = request.user
    base = "/operacao" if user.eh_operacao else "/portal"
    lista = [
        {
            "id": str(n.id),
            "mensagem": n.mensagem,
            "lida": n.lida,
            "quando": tempo_relativo(n.criado_em),
            "href": f"{base}/{n.ocorrencia_id}" if n.ocorrencia_id else None,
            "icone": icone(n.mensagem)[0],
            "cor": icone(n.mensagem)[1],
        }
        for n in user.notificacoes.order_by("-criado_em")[:6]
    ]
    return JsonResponse({"itens": lista, "naoLidas": user.notificacoes.filter(lida=False).count()})


@login_required
@require_POST
def marcar_lidas(request):
    """Marca como lidas só as notificações que o usuário de fato viu (`ids`)."""
    ids = uuids_validos(request.POST.getlist("ids"))
    if ids:
        request.user.notificacoes.filter(lida=False, pk__in=ids).update(lida=True)
    return JsonResponse({"ok": True})
