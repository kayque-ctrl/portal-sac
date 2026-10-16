from django.urls import path

from .views import comum, cron, operacao, portal, publico

publico_urls = [
    path("", publico.inicio, name="inicio"),
    path("consulta", publico.consulta, name="consulta"),
    path("anexos/<uuid:pk>", comum.baixar_anexo, name="anexo"),
    path("notificacoes/recentes", comum.notificacoes_recentes, name="notificacoes_recentes"),
    path("notificacoes/marcar-lidas", comum.marcar_lidas, name="marcar_lidas"),
    path("notificacoes/marcar-todas", comum.marcar_todas_lidas, name="marcar_todas_lidas"),
    path("cron/arquivar", cron.arquivar, name="cron_arquivar"),
]

portal_urls = (
    [
        path("", portal.inicio, name="inicio"),
        path("ocorrencias", portal.lista, name="lista"),
        path("dashboard", portal.dashboard, name="dashboard"),
        path("notificacoes", portal.notificacoes, name="notificacoes"),
        path("nova", portal.nova, name="nova"),
        path("nova/importar", portal.importar, name="importar"),
        path("nova/duplicata", portal.verificar_duplicata, name="duplicata"),
        path("<uuid:pk>", portal.detalhe, name="detalhe"),
        path("<uuid:pk>/mensagem", portal.enviar_mensagem, name="mensagem"),
        path("<uuid:pk>/aprovar", portal.aprovar, name="aprovar"),
        path("<uuid:pk>/reabrir", portal.reabrir, name="reabrir"),
        path("<uuid:pk>/export", portal.exportar, name="exportar"),
    ],
    "portal",
)

operacao_urls = (
    [
        path("", operacao.lista, name="lista"),
        path("lixeira/esvaziar", operacao.esvaziar_lixeira, name="esvaziar_lixeira"),
        path("lixeira/excluir", operacao.excluir_selecionadas, name="excluir_selecionadas"),
        path("painel", operacao.painel, name="painel"),
        path("painel/export", operacao.painel_exportar, name="painel_exportar"),
        path("notificacoes", operacao.notificacoes, name="notificacoes"),
        path("empresas", operacao.empresas, name="empresas"),
        path("empresas/<uuid:pk>", operacao.empresa_detalhe, name="empresa_detalhe"),
        path("usuarios", operacao.usuarios, name="usuarios"),
        path("usuarios/<uuid:pk>", operacao.usuario_detalhe, name="usuario_detalhe"),
        path("usuarios/<uuid:pk>/excluir", operacao.usuario_excluir, name="usuario_excluir"),
        path("usuarios/<uuid:pk>/reenviar", operacao.usuario_reenviar, name="usuario_reenviar"),
        path("avisos", operacao.avisos, name="avisos"),
        path("avisos/<uuid:pk>/<str:acao>", operacao.aviso_acao, name="aviso_acao"),
        path("contatos", operacao.contatos, name="contatos"),
        path("contatos/<uuid:pk>/<str:acao>", operacao.contato_acao, name="contato_acao"),
        path("sla", operacao.sla, name="sla"),
        path("sla/<uuid:pk>/excluir", operacao.sla_excluir, name="sla_excluir"),
        path("<uuid:pk>", operacao.detalhe, name="detalhe"),
        path("<uuid:pk>/atualizar", operacao.atualizar, name="atualizar"),
        path("<uuid:pk>/mensagem", operacao.enviar_mensagem, name="mensagem"),
        path("<uuid:pk>/coleta", operacao.solicitar_coleta, name="coleta"),
        path("<uuid:pk>/ciclo/<str:acao>", operacao.ciclo_vida, name="ciclo"),
        path("<uuid:pk>/export", operacao.exportar, name="exportar"),
    ],
    "operacao",
)
