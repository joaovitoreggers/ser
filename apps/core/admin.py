from django.contrib import admin

from .models import LogAuditoria, Restaurante


@admin.register(Restaurante)
class RestauranteAdmin(admin.ModelAdmin):
    list_display = ("nome", "cnpj", "margem_padrao", "ativo", "criado_em")
    list_filter = ("ativo",)
    search_fields = ("nome", "cnpj")


@admin.register(LogAuditoria)
class LogAuditoriaAdmin(admin.ModelAdmin):
    list_display = ("acao", "entidade", "entidade_id", "usuario", "criado_em")
    list_filter = ("entidade",)
    search_fields = ("acao", "entidade")
    readonly_fields = (
        "restaurante",
        "usuario",
        "acao",
        "entidade",
        "entidade_id",
        "dados_antes",
        "dados_depois",
        "ip",
        "criado_em",
    )
