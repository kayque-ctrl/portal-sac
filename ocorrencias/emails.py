"""
E-mail transacional best-effort. Só envia de verdade com SMTP configurado
(ver settings.SMTP_CONFIGURADO); sem ele, o conteúdo vai para o console e a
função devolve False. Nunca lança exceção.
"""

import logging

from django.conf import settings
from django.core.mail import EmailMessage
from django.utils.html import escape

log = logging.getLogger("ocorrencias")


def enviar_email(to: str, subject: str, html: str) -> bool:
    """Retorna True se o e-mail foi de fato enviado (SMTP configurado e sem erro)."""
    if not to:
        return False
    try:
        msg = EmailMessage(subject=subject, body=html, from_email=settings.DEFAULT_FROM_EMAIL, to=[to])
        msg.content_subtype = "html"
        msg.send(fail_silently=False)
    except Exception as e:  # noqa: BLE001 — best-effort, nunca quebra o fluxo
        log.warning("[email] erro ao enviar: %s", e)
        return False
    return bool(settings.SMTP_CONFIGURADO)


def botao_email(href: str, texto: str) -> str:
    """Botão estilizado para um link absoluto (ex.: convite/redefinição com token)."""
    return (
        f'<p style="margin:24px 0"><a href="{escape(href)}" style="background:#18181b;color:#fff;'
        f'text-decoration:none;padding:10px 18px;border-radius:8px;font-size:14px">{escape(texto)}</a></p>'
    )


def layout_email(titulo: str, corpo: str, cta: str | None = None) -> str:
    """Layout simples e neutro. `corpo` é HTML confiável montado pelo código."""
    botao = botao_email(f"{settings.SITE_URL}{cta}", "Ver no portal") if cta else ""
    return (
        '<div style="font-family:Arial,Helvetica,sans-serif;max-width:520px;margin:0 auto;color:#18181b">'
        f'<h2 style="font-size:18px;margin:0 0 12px">{escape(titulo)}</h2>'
        f'<div style="font-size:14px;line-height:1.6;color:#3f3f46">{corpo}</div>'
        f"{botao}"
        '<p style="font-size:12px;color:#a1a1aa;margin-top:28px">Portal de Ocorrências</p>'
        "</div>"
    )
