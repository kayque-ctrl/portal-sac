"""Regras de upload: limites, tipos aceitos e checagem de conteúdo."""

import re

MAX_ANEXOS = 5
MAX_TAMANHO_BYTES = 10 * 1024 * 1024  # 10 MB

TIPOS_PERMITIDOS = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/gif",
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",  # .xlsx
    "application/vnd.ms-excel",  # .xls (e às vezes .csv)
    "text/csv",
}

EXTENSOES_PERMITIDAS = {"jpg", "jpeg", "png", "webp", "gif", "pdf", "xlsx", "xls", "csv"}

ACCEPT_ATTR = ".jpg,.jpeg,.png,.webp,.gif,.pdf,.xlsx,.xls,.csv"


def anexo_permitido(nome: str, mime: str) -> bool:
    """Aceita pelo MIME ou pela extensão (CSV/XLS podem vir com MIME inconsistente)."""
    if mime in TIPOS_PERMITIDOS:
        return True
    ext = nome.rsplit(".", 1)[-1].lower() if "." in nome else ""
    return ext in EXTENSOES_PERMITIDAS


def conteudo_imagem_confere(arquivo) -> bool:
    """
    Confere se um arquivo declarado como imagem tem, de fato, assinatura
    (magic bytes) de imagem — evita um arquivo malicioso renomeado.
    Para não-imagens, não bloqueia.
    """
    if not (arquivo.content_type or "").startswith("image/"):
        return True
    try:
        pos = arquivo.tell()
        arquivo.seek(0)
        b = arquivo.read(12)
        arquivo.seek(pos)
    except Exception:  # noqa: BLE001
        return True
    if b[:3] == b"\xff\xd8\xff":  # JPEG
        return True
    if b[:4] == b"\x89PNG":  # PNG
        return True
    if b[:3] == b"GIF":
        return True
    if b[:2] == b"BM":  # BMP
        return True
    if b[:4] == b"RIFF" and b[8:12] == b"WEBP":
        return True
    return False


def validar_arquivos(arquivos) -> str | None:
    """Valida a lista de anexos; devolve a mensagem de erro ou None."""
    if len(arquivos) > MAX_ANEXOS:
        return f"Envie no máximo {MAX_ANEXOS} anexos."
    for a in arquivos:
        if a.size > MAX_TAMANHO_BYTES:
            return f'"{a.name}" excede o limite de 10 MB.'
        if not anexo_permitido(a.name, a.content_type or ""):
            return f'"{a.name}" tem um formato não permitido.'
        if not conteudo_imagem_confere(a):
            return f'"{a.name}" não parece uma imagem válida.'
    return None


def sanitizar_nome(nome: str) -> str:
    """Nome seguro para o disco. O original (com acentos) fica em nome_arquivo."""
    idx = nome.rfind(".")
    base, ext = (nome[:idx], nome[idx:]) if idx > 0 else (nome, "")
    base_slug = re.sub(r"[^a-zA-Z0-9_-]", "_", base)[:60] or "arquivo"
    ext_slug = re.sub(r"[^a-z0-9.]", "", ext.lower())
    return base_slug + ext_slug
