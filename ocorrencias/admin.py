from django.contrib import admin

from .models import (
    Anexo,
    Aviso,
    ContatoEncaminhamento,
    HistoricoStatus,
    Mensagem,
    Notificacao,
    Ocorrencia,
    OcorrenciaItem,
    SlaRegra,
)


class ItemInline(admin.TabularInline):
    model = OcorrenciaItem
    extra = 0


class HistoricoInline(admin.TabularInline):
    model = HistoricoStatus
    extra = 0
    readonly_fields = ["de_status", "para_status", "alterado_por", "criado_em"]
    can_delete = False


@admin.register(Ocorrencia)
class OcorrenciaAdmin(admin.ModelAdmin):
    list_display = ["protocolo", "cliente", "tipo", "status", "prioridade", "criado_em"]
    list_filter = ["status", "tipo", "prioridade"]
    search_fields = ["protocolo", "descricao", "referencia", "cliente__nome"]
    readonly_fields = ["protocolo", "sla_horas", "sla_prazo", "sla_restante_ms", "sla_cumprido"]
    inlines = [ItemInline, HistoricoInline]

    def save_model(self, request, obj, form, change):
        obj.save(por=request.user)


admin.site.register(Mensagem)
admin.site.register(Anexo)
admin.site.register(Notificacao)
admin.site.register(Aviso)
admin.site.register(SlaRegra)
admin.site.register(ContatoEncaminhamento)
