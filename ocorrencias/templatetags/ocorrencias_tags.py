from urllib.parse import urlencode

from django import template
from django.utils.html import format_html

from .. import formato, labels, notificacoes
from ..sla import SLA_COR, SLA_ICONE, calcular_sla

register = template.Library()


# ---------- rótulos ----------


@register.filter
def tipo_label(v):
    return labels.TIPO_LABEL.get(v, v)


@register.filter
def status_label(v):
    return labels.STATUS_LABEL.get(v, v)


@register.filter
def prioridade_label(v):
    return labels.PRIORIDADE_LABEL.get(v, v)


@register.filter
def categoria_label(v):
    return labels.ITEM_CATEGORIA_LABEL.get(v, v)


@register.filter
def prioridade_badge(v):
    return labels.PRIORIDADE_BADGE.get(v, "")


@register.filter
def papel_badge(v):
    return labels.PAPEL_BADGE.get(v, "")


@register.filter
def item_badge(v):
    return labels.ITEM_BADGE.get(v, "")


@register.filter
def status_dot(v):
    return labels.STATUS_DOT.get(v, "bg-zinc-400")


@register.filter
def referencia(oc):
    return labels.formatar_referencia(oc.referencia_tipo, oc.referencia)


# ---------- formatação ----------


@register.filter
def data(dt):
    return formato.formatar_data(dt)


@register.filter
def dia(dt):
    return formato.formatar_dia(dt)


@register.filter
def relativo(dt):
    return formato.tempo_relativo(dt)


@register.filter
def tamanho(n):
    return formato.formatar_tamanho(n)


@register.filter
def get(d, chave):
    """{{ dicionario|get:"chave" }} (também funciona com QueryDict)."""
    try:
        return d.get(chave, "")
    except AttributeError:
        return ""


@register.filter
def plural(n, formas):
    """{{ n|plural:"ocorrência,ocorrências" }}"""
    um, varios = formas.split(",")
    return um if n == 1 else varios


# ---------- componentes ----------


@register.simple_tag
def icone(nome, tamanho=16, classe=""):
    """Ícone Lucide (o script troca o <i> pelo SVG)."""
    return format_html(
        '<i data-lucide="{}" aria-hidden="true" class="inline-block shrink-0 {}" style="width:{}px;height:{}px"></i>',
        nome,
        classe,
        tamanho,
        tamanho,
    )


@register.simple_tag
def status_badge(status):
    return format_html(
        '<span class="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset {}">{}</span>',
        labels.STATUS_BADGE.get(status, ""),
        labels.STATUS_LABEL.get(status, status),
    )


@register.simple_tag
def sla_badge(oc):
    sla = calcular_sla(oc)
    if sla.estado == "sem_sla":
        return ""
    return format_html(
        '<span class="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset {}">{}{}</span>',
        SLA_COR[sla.estado],
        icone(SLA_ICONE[sla.estado], 12),
        sla.label,
    )


@register.simple_tag
def notif_icone(mensagem, tamanho=16):
    nome, cor = notificacoes.icone(mensagem)
    return format_html(
        '<span class="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-zinc-100 dark:bg-zinc-800 {}">{}</span>',
        cor,
        icone(nome, tamanho),
    )


FLUXO = ["aberta", "em_analise", "resolvida", "concluida"]


@register.inclusion_tag("ocorrencias/partials/stepper.html")
def andamento(status):
    """Passos da trilha visual do status."""
    if status == "recusada":
        # Desfecho recusado: Aberta → Em tratativa → Recusada.
        passos = [
            {"label": labels.STATUS_LABEL["aberta"], "estado": "feito", "linha": "bg-zinc-300 dark:bg-zinc-700"},
            {"label": labels.STATUS_LABEL["em_analise"], "estado": "feito", "linha": "bg-red-300 dark:bg-red-900/60"},
            {"label": labels.STATUS_LABEL["recusada"], "estado": "recusado"},
        ]
    else:
        atual = FLUXO.index(status) if status in FLUXO else 0
        passos = [
            {
                "label": labels.STATUS_LABEL[s],
                "estado": "feito" if i < atual else "atual" if i == atual else "futuro",
                "linha": "bg-zinc-900 dark:bg-white" if i < atual else "bg-zinc-300 dark:bg-zinc-700",
            }
            for i, s in enumerate(FLUXO)
        ]
    for i, p in enumerate(passos):
        p["numero"] = i + 1
        p["ultimo"] = i == len(passos) - 1
    return {"passos": passos}


@register.simple_tag(takes_context=True)
def url_com(context, **kwargs):
    """Querystring atual trocando/removendo chaves (valor vazio remove)."""
    params = context["request"].GET.copy()
    for k, v in kwargs.items():
        if v in (None, ""):
            params.pop(k, None)
        else:
            params[k] = v
    qs = params.urlencode()
    return f"?{qs}" if qs else "?"


@register.simple_tag
def query(**kwargs):
    return urlencode({k: v for k, v in kwargs.items() if v})
