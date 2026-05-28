from django.contrib import admin

from .models import FichaIngrediente, FichaTecnica, FichaTecnicaVersao


class FichaIngredienteInline(admin.TabularInline):
    model = FichaIngrediente
    extra = 1
    autocomplete_fields = ("ingrediente",)


@admin.register(FichaTecnica)
class FichaTecnicaAdmin(admin.ModelAdmin):
    list_display = (
        "nome",
        "restaurante",
        "rendimento",
        "custo_total",
        "custo_porcao",
        "versao",
        "ativo",
    )
    list_filter = ("restaurante", "ativo")
    search_fields = ("nome",)
    autocomplete_fields = ("restaurante",)
    readonly_fields = ("custo_total", "custo_porcao")
    inlines = (FichaIngredienteInline,)


@admin.register(FichaTecnicaVersao)
class FichaTecnicaVersaoAdmin(admin.ModelAdmin):
    list_display = ("ficha", "versao")
    search_fields = ("ficha__nome",)
