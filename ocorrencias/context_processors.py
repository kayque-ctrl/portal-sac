"""Dados da casca das áreas internas: menus, sino e contadores (specs 022 e 023)."""

# (href, rótulo, ícone Lucide). O grupo vira o título no menu lateral da operação.
MENU_OPERACAO = [
    (
        "Atendimento",
        [
            ("/operacao/", "Ocorrências", "inbox"),
            ("/operacao/painel", "Painel", "bar-chart-3"),
        ],
    ),
    (
        "Cadastros",
        [
            ("/operacao/empresas", "Empresas", "building-2"),
            ("/operacao/transportadoras", "Transportadoras", "truck"),
            ("/operacao/usuarios", "Usuários", "users"),
            ("/operacao/avisos", "Avisos", "megaphone"),
            ("/operacao/contatos", "Contatos", "mail"),
        ],
    ),
]
MENU_ADMIN = ("Administração", [("/operacao/sla", "Prazos (SLA)", "timer")])

# O cliente também navega pelo menu lateral (spec 030, como a interface simplificada do GLPI).
MENU_CLIENTE = [
    (
        "Atendimento",
        [
            ("/portal/", "Início", "house"),
            ("/portal/nova", "Abrir ocorrência", "plus"),
            ("/portal/ocorrencias", "Minhas ocorrências", "inbox"),
            ("/portal/dashboard", "Painel", "bar-chart-3"),
        ],
    ),
]


def _atual(path: str, grupos, padrao: str | None = None) -> str | None:
    """
    O link do menu que fica ativo. Casa o prefixo mais longo; a raiz da área só
    vale para ela mesma, e o resto (ex.: o detalhe de uma ocorrência) cai no
    `padrao`. Notificações não marcam nada: têm o sino.
    """
    if path.rstrip("/").endswith("/notificacoes"):
        return None
    hrefs = [href for _, links in grupos for href, _, _ in links]
    especificos = [h for h in hrefs if not h.endswith("/") and path.startswith(h)]
    if especificos:
        return max(especificos, key=len)
    if path in hrefs:
        return path
    return padrao


def cabecalho(request):
    """Menu da área, contador do sino e quantas ocorrências estão ativas (operação)."""
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated or not request.path.startswith(("/portal", "/operacao")):
        return {}

    if user.eh_operacao:
        grupos = MENU_OPERACAO + ([MENU_ADMIN] if user.eh_admin else [])
        padrao = "/operacao/"
    else:
        grupos = MENU_CLIENTE
        padrao = "/portal/ocorrencias"

    contexto = {
        "area_base": "/operacao" if user.eh_operacao else "/portal",
        "notif_nao_lidas": user.notificacoes.filter(lida=False).count(),
        "menu": grupos,
        "menu_atual": _atual(request.path, grupos, padrao),
        "na_notificacoes": request.path.rstrip("/").endswith("/notificacoes"),
    }
    if user.eh_operacao:
        from .labels import STATUS_ATIVOS
        from .models import Ocorrencia

        contexto["qtd_ativas"] = Ocorrencia.objects.filter(
            status__in=STATUS_ATIVOS, arquivada_em__isnull=True, excluida_em__isnull=True
        ).count()
    return contexto
