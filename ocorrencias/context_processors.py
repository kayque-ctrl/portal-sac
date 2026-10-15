NAV_OPERACAO = [
    ("/operacao/", "Ocorrências"),
    ("/operacao/painel", "Painel"),
    ("/operacao/empresas", "Empresas"),
    ("/operacao/usuarios", "Usuários"),
    ("/operacao/avisos", "Avisos"),
    ("/operacao/contatos", "Contatos"),
]


def cabecalho(request):
    """Dados do cabeçalho das áreas internas (navegação e sino de notificações)."""
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated or not request.path.startswith(("/portal", "/operacao")):
        return {}

    contexto = {
        "area_base": "/operacao" if user.eh_operacao else "/portal",
        "notif_nao_lidas": user.notificacoes.filter(lida=False).count(),
    }
    if user.eh_operacao:
        links = NAV_OPERACAO + ([("/operacao/sla", "SLA")] if user.eh_admin else [])
        # A aba "Ocorrências" fica ativa em tudo que não for outra seção.
        atual = next((href for href, _ in links[1:] if request.path.startswith(href)), "/operacao/")
        if request.path.startswith("/operacao/notificacoes"):
            atual = None
        contexto.update(nav_operacao=links, nav_atual=atual)
    return contexto
