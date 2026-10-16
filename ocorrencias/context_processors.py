"""Dados da casca das áreas internas: menu lateral, barra de baixo e sino (spec 022)."""

# (href, rótulo, ícone Lucide). O grupo vira o título no menu lateral.
MENU_OPERACAO = [
    (
        "Atendimento",
        [
            ("/operacao/", "Ocorrências", "clipboard-list"),
            ("/operacao/painel", "Painel", "bar-chart-3"),
        ],
    ),
    (
        "Cadastros",
        [
            ("/operacao/empresas", "Empresas", "building-2"),
            ("/operacao/usuarios", "Usuários", "users"),
            ("/operacao/avisos", "Avisos", "megaphone"),
            ("/operacao/contatos", "Contatos", "mail"),
        ],
    ),
]
MENU_ADMIN = ("Administração", [("/operacao/sla", "Prazos (SLA)", "timer")])

MENU_CLIENTE = [
    (
        None,
        [
            ("/portal/", "Ocorrências", "clipboard-list"),
            ("/portal/dashboard", "Painel", "bar-chart-3"),
        ],
    ),
]


def _atual(path: str, grupos) -> str | None:
    """O link mais específico que casa com a URL; a raiz da área vale para o resto."""
    hrefs = [href for _, links in grupos for href, _, _ in links]
    if path.rstrip("/").endswith("/notificacoes"):
        return None
    especificos = [h for h in hrefs if not h.endswith("/") and path.startswith(h)]
    if especificos:
        return max(especificos, key=len)
    return next((h for h in hrefs if h.endswith("/")), None)


def cabecalho(request):
    """Menu da área, contador do sino e quantas ocorrências estão ativas (operação)."""
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated or not request.path.startswith(("/portal", "/operacao")):
        return {}

    if user.eh_operacao:
        grupos = MENU_OPERACAO + ([MENU_ADMIN] if user.eh_admin else [])
    else:
        grupos = MENU_CLIENTE

    contexto = {
        "area_base": "/operacao" if user.eh_operacao else "/portal",
        "notif_nao_lidas": user.notificacoes.filter(lida=False).count(),
        "menu": grupos,
        "menu_atual": _atual(request.path, grupos),
        "na_notificacoes": request.path.rstrip("/").endswith("/notificacoes"),
    }
    if user.eh_operacao:
        from .labels import STATUS_ATIVOS
        from .models import Ocorrencia

        contexto["qtd_ativas"] = Ocorrencia.objects.filter(
            status__in=STATUS_ATIVOS, arquivada_em__isnull=True, excluida_em__isnull=True
        ).count()
    return contexto
