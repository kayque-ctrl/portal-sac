from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Empresa, Usuario


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    ordering = ["nome"]
    list_display = ["nome", "email", "papel", "empresa", "ativado_em", "is_active"]
    list_filter = ["papel", "is_active", "empresa"]
    search_fields = ["nome", "email", "documento"]
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Perfil", {"fields": ("nome", "papel", "tipo_pessoa", "documento", "telefone", "empresa", "ativado_em")}),
        ("Permissões", {"fields": ("is_active", "is_staff", "is_superuser")}),
    )
    add_fieldsets = ((None, {"classes": ("wide",), "fields": ("email", "nome", "papel", "password1", "password2")}),)


@admin.register(Empresa)
class EmpresaAdmin(admin.ModelAdmin):
    list_display = ["nome", "cnpj", "contato_nome", "contato_email", "telefone"]
    search_fields = ["nome", "cnpj"]
