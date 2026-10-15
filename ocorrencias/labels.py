"""Enums do domínio, rótulos, cores de badge e listas de opções derivadas."""

from django.db import models


class OcorrenciaTipo(models.TextChoices):
    PRODUTOS = "produtos", "Problemas com produtos"
    ATRASO = "atraso", "Atraso na entrega"
    RECLAMACAO_SUGESTAO = "reclamacao_sugestao", "Reclamação / Sugestão"
    # legado (categorias que antes eram o tipo da ocorrência, hoje são do produto):
    AVARIA = "avaria", "Avaria"
    FALTA = "falta", "Falta"
    SOBRA = "sobra", "Sobra"
    TROCA_VOLUME = "troca_volume", "Troca de volume"
    EXTRAVIO = "extravio", "Extravio"
    FALTA_TROCA = "falta_troca", "Falta / Troca de volume"
    OUTRO = "outro", "Outro"


class ItemCategoria(models.TextChoices):
    """Categoria de cada produto dentro de uma ocorrência do tipo "produtos"."""

    AVARIA = "avaria", "Avaria"
    FALTA = "falta", "Falta"
    SOBRA = "sobra", "Sobra"
    TROCA_VOLUME = "troca_volume", "Troca de volume"
    VENCIDO = "vencido", "Vencido"
    PRE_VENCIDO = "pre_vencido", "Pré-vencido"


class SinalVolume(models.TextChoices):
    """Na troca de volume: o volume está faltando ou sobrando (spec 004)."""

    FALTA = "falta", "Falta"
    SOBRA = "sobra", "Sobra"


class ReferenciaTipo(models.TextChoices):
    NF = "nf", "Nota Fiscal"
    PEDIDO = "pedido", "Pedido"


class Status(models.TextChoices):
    ABERTA = "aberta", "Aberta"
    EM_ANALISE = "em_analise", "Em tratativa"
    RESOLVIDA = "resolvida", "Aguardando aprovação"
    CONCLUIDA = "concluida", "Resolvida"
    RECUSADA = "recusada", "Recusada"


class Prioridade(models.TextChoices):
    BAIXA = "baixa", "Baixa"
    MEDIA = "media", "Média"
    ALTA = "alta", "Alta"


class AvisoTipo(models.TextChoices):
    INFO = "info", "Info"
    ALERTA = "alerta", "Alerta"


TIPO_LABEL = dict(OcorrenciaTipo.choices)
STATUS_LABEL = dict(Status.choices)
PRIORIDADE_LABEL = dict(Prioridade.choices)
ITEM_CATEGORIA_LABEL = dict(ItemCategoria.choices)
REFERENCIA_LABEL = dict(ReferenciaTipo.choices)

# Tipos oferecidos ao abrir uma ocorrência.
TIPOS_FORM = [OcorrenciaTipo.PRODUTOS, OcorrenciaTipo.ATRASO, OcorrenciaTipo.RECLAMACAO_SUGESTAO]

# Tipos que exigem referência (NF ou Pedido).
CATEGORIAS_COM_REFERENCIA = [OcorrenciaTipo.PRODUTOS, OcorrenciaTipo.ATRASO]

# Tipos em que se lançam produtos.
CATEGORIAS_COM_PRODUTOS = [OcorrenciaTipo.PRODUTOS]

ITEM_CATEGORIAS = list(ItemCategoria.values)

# Categorias em que pelo menos uma foto nos anexos é obrigatória.
CATEGORIAS_EXIGEM_FOTO = ["avaria", "vencido", "pre_vencido", "troca_volume"]

# Categorias em que o cliente nem abriu o produto (troca de volume): código,
# descrição e quantidade detalhados deixam de ser obrigatórios.
CATEGORIAS_DISPENSAM_DADOS_PRODUTO = ["troca_volume"]

# Categorias em que o cliente informa se o volume falta ou sobra (spec 004).
CATEGORIAS_COM_SINAL_VOLUME = ["troca_volume"]

# Status em que a conversa fica bloqueada (só reabrindo volta a enviar).
STATUS_BLOQUEADOS = [Status.RESOLVIDA, Status.CONCLUIDA, Status.RECUSADA]
STATUS_ATIVOS = [Status.ABERTA, Status.EM_ANALISE]
STATUS_ENCERRADOS = [Status.RESOLVIDA, Status.CONCLUIDA, Status.RECUSADA]

# Ordem dos chips de status no portal.
STATUS_ORDEM = [s.value for s in Status]

# Limites para o aviso caber legível no painel (mensagem em até 2 linhas).
AVISO_TITULO_MAX = 60
AVISO_MENSAGEM_MAX = 160

# ---------- Classes Tailwind ----------

STATUS_BADGE = {
    "aberta": "bg-blue-50 text-blue-700 ring-blue-600/20 dark:bg-blue-950/40 dark:text-blue-300 dark:ring-blue-400/20",
    "em_analise": "bg-yellow-50 text-yellow-700 ring-yellow-600/20 dark:bg-yellow-950/40 dark:text-yellow-300 dark:ring-yellow-400/20",
    "resolvida": "bg-amber-50 text-amber-700 ring-amber-600/20 dark:bg-amber-950/40 dark:text-amber-300 dark:ring-amber-400/20",
    "concluida": "bg-green-50 text-green-700 ring-green-600/20 dark:bg-green-950/40 dark:text-green-300 dark:ring-green-400/20",
    "recusada": "bg-zinc-100 text-zinc-600 ring-zinc-500/20 dark:bg-zinc-800 dark:text-zinc-400 dark:ring-zinc-400/20",
}

# Bolinha de status nos chips e nas linhas do portal.
STATUS_DOT = {
    "todas": "bg-zinc-400",
    "aberta": "bg-blue-500",
    "em_analise": "bg-yellow-400",
    "resolvida": "bg-amber-500",
    "concluida": "bg-green-500",
    "recusada": "bg-zinc-400",
}

PRIORIDADE_BADGE = {
    "baixa": "bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400",
    "media": "bg-sky-50 text-sky-700 dark:bg-sky-950/40 dark:text-sky-300",
    "alta": "bg-red-50 text-red-700 dark:bg-red-950/40 dark:text-red-300",
}

ITEM_BADGE = {
    "avaria": "bg-amber-50 text-amber-700 dark:bg-amber-950/40 dark:text-amber-300",
    "falta": "bg-red-50 text-red-700 dark:bg-red-950/40 dark:text-red-300",
    "sobra": "bg-green-50 text-green-700 dark:bg-green-950/40 dark:text-green-300",
    "troca_volume": "bg-blue-50 text-blue-700 dark:bg-blue-950/40 dark:text-blue-300",
    "vencido": "bg-rose-50 text-rose-700 dark:bg-rose-950/40 dark:text-rose-300",
    "pre_vencido": "bg-orange-50 text-orange-700 dark:bg-orange-950/40 dark:text-orange-300",
}

# Cor da FONTE da descrição do produto (spec 006): só as categorias pedidas no
# card, nos mesmos tons das etiquetas. As demais seguem o texto padrão.
ITEM_TEXTO = {
    "avaria": "text-amber-700 dark:text-amber-400",
    "pre_vencido": "text-orange-700 dark:text-orange-400",
    "vencido": "text-rose-700 dark:text-rose-400",
}
ITEM_TEXTO_PADRAO = "text-zinc-800 dark:text-zinc-200"

PAPEL_BADGE = {
    "admin": "bg-amber-50 text-amber-700 dark:bg-amber-950/40 dark:text-amber-300",
    "operador": "bg-violet-50 text-violet-700 dark:bg-violet-950/40 dark:text-violet-300",
    "cliente": "bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-300",
}


def sinal_categoria(cat: str | None) -> str:
    """Sinal do item conforme a categoria: falta = neg, sobra = pos, resto = neutro."""
    if cat == "falta":
        return "neg"
    if cat == "sobra":
        return "pos"
    return "neutro"


def sinal_item(categoria: str | None, sinal_volume: str | None = None) -> str:
    """Sinal de um item: falta/sobra pela categoria; na troca de volume, pelo sinal informado."""
    if categoria in CATEGORIAS_COM_SINAL_VOLUME:
        return sinal_categoria(sinal_volume)
    return sinal_categoria(categoria)


def rotulo_item(categoria: str | None, sinal_volume: str | None = None) -> str:
    """Ex.: "Avaria" ou "Troca de volume (falta)"."""
    rotulo = ITEM_CATEGORIA_LABEL.get(categoria, categoria or "")
    if categoria in CATEGORIAS_COM_SINAL_VOLUME and sinal_volume in SinalVolume.values:
        return f"{rotulo} ({SinalVolume(sinal_volume).label.lower()})"
    return rotulo


def formatar_referencia(tipo: str | None, referencia: str | None) -> str:
    """Ex.: "NF 12345" ou "Pedido 987"."""
    if not referencia:
        return ""
    if tipo == "nf":
        return f"NF {referencia}"
    if tipo == "pedido":
        return f"Pedido {referencia}"
    return referencia
