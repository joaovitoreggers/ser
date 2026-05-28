from django.contrib import admin

from .models import (
    AjusteEstoque,
    CategoriaIngrediente,
    EntradaEstoque,
    Fornecedor,
    Ingrediente,
)


@admin.register(CategoriaIngrediente)
class CategoriaIngredienteAdmin(admin.ModelAdmin):
    list_display = ("nome", "restaurante")
    list_filter = ("restaurante",)
    search_fields = ("nome",)


@admin.register(Ingrediente)
class IngredienteAdmin(admin.ModelAdmin):
    list_display = (
        "nome",
        "restaurante",
        "categoria",
        "unidade_medida",
        "estoque_atual",
        "estoque_minimo",
        "custo_unitario",
        "ativo",
    )
    list_filter = ("restaurante", "ativo", "unidade_medida")
    search_fields = ("nome",)
    autocomplete_fields = ("restaurante", "categoria")


@admin.register(Fornecedor)
class FornecedorAdmin(admin.ModelAdmin):
    list_display = ("nome", "restaurante", "cnpj", "ativo")
    list_filter = ("restaurante", "ativo")
    search_fields = ("nome", "cnpj")


@admin.register(EntradaEstoque)
class EntradaEstoqueAdmin(admin.ModelAdmin):
    list_display = (
        "ingrediente",
        "quantidade",
        "custo_unitario",
        "fornecedor",
        "data_entrada",
    )
    list_filter = ("restaurante", "data_entrada")
    search_fields = ("ingrediente__nome", "nota_fiscal")
    autocomplete_fields = ("restaurante", "ingrediente", "fornecedor", "usuario")


@admin.register(AjusteEstoque)
class AjusteEstoqueAdmin(admin.ModelAdmin):
    list_display = ("ingrediente", "qtd_anterior", "qtd_nova", "motivo", "criado_em")
    list_filter = ("restaurante", "motivo")
    search_fields = ("ingrediente__nome",)
    autocomplete_fields = ("restaurante", "ingrediente", "usuario")
