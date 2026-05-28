from django.contrib import admin

from .models import CategoriaPrato, HistoricoPreco, Prato


@admin.register(CategoriaPrato)
class CategoriaPratoAdmin(admin.ModelAdmin):
    list_display = ("nome", "restaurante", "ordem", "hora_inicio", "hora_fim")
    list_filter = ("restaurante",)
    search_fields = ("nome",)


@admin.register(Prato)
class PratoAdmin(admin.ModelAdmin):
    list_display = (
        "nome",
        "restaurante",
        "categoria",
        "preco_venda",
        "custo_atual",
        "margem_lucro",
        "disponivel",
    )
    list_filter = ("restaurante", "disponivel", "categoria")
    search_fields = ("nome",)
    autocomplete_fields = ("restaurante", "ficha", "categoria")
    readonly_fields = ("custo_atual", "margem_lucro")


@admin.register(HistoricoPreco)
class HistoricoPrecoAdmin(admin.ModelAdmin):
    list_display = ("prato", "preco_anterior", "preco_novo", "usuario", "criado_em")
    search_fields = ("prato__nome",)
    readonly_fields = ("prato", "preco_anterior", "preco_novo", "usuario", "criado_em")
