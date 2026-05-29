from __future__ import annotations

from django.urls import path

from . import views

app_name = "estoque"

urlpatterns = [
    # Ingredientes (home do módulo)
    path("", views.IngredienteListView.as_view(), name="home"),
    # Categorias de ingrediente
    path(
        "categorias/",
        views.CategoriaIngredienteListView.as_view(),
        name="categoria_list",
    ),
    path(
        "categorias/tabela/",
        views.CategoriaIngredienteTabelaView.as_view(),
        name="categoria_tabela",
    ),
    path(
        "categorias/novo/",
        views.CategoriaIngredienteCreateView.as_view(),
        name="categoria_novo",
    ),
    path(
        "categorias/<uuid:pk>/editar/",
        views.CategoriaIngredienteUpdateView.as_view(),
        name="categoria_editar",
    ),
    path(
        "categorias/<uuid:pk>/excluir/",
        views.CategoriaIngredienteDeleteView.as_view(),
        name="categoria_excluir",
    ),
    path("ingredientes/", views.IngredienteListView.as_view(), name="ingrediente_list"),
    path(
        "ingredientes/tabela/",
        views.IngredienteTabelaView.as_view(),
        name="ingrediente_tabela",
    ),
    path(
        "ingredientes/novo/",
        views.IngredienteCreateView.as_view(),
        name="ingrediente_novo",
    ),
    path(
        "ingredientes/<uuid:pk>/editar/",
        views.IngredienteUpdateView.as_view(),
        name="ingrediente_editar",
    ),
    path(
        "ingredientes/<uuid:pk>/excluir/",
        views.IngredienteDeleteView.as_view(),
        name="ingrediente_excluir",
    ),
    # Fornecedores
    path("fornecedores/", views.FornecedorListView.as_view(), name="fornecedor_list"),
    path(
        "fornecedores/tabela/",
        views.FornecedorTabelaView.as_view(),
        name="fornecedor_tabela",
    ),
    path(
        "fornecedores/novo/",
        views.FornecedorCreateView.as_view(),
        name="fornecedor_novo",
    ),
    path(
        "fornecedores/<uuid:pk>/editar/",
        views.FornecedorUpdateView.as_view(),
        name="fornecedor_editar",
    ),
    path(
        "fornecedores/<uuid:pk>/excluir/",
        views.FornecedorDeleteView.as_view(),
        name="fornecedor_excluir",
    ),
    # Entradas de estoque
    path("entradas/", views.EntradaEstoqueListView.as_view(), name="entrada_list"),
    path(
        "entradas/tabela/",
        views.EntradaEstoqueTabelaView.as_view(),
        name="entrada_tabela",
    ),
    path("entradas/nova/", views.EntradaEstoqueCreateView.as_view(), name="entrada_nova"),
    # Ajustes de estoque
    path("ajustes/", views.AjusteEstoqueListView.as_view(), name="ajuste_list"),
    path("ajustes/tabela/", views.AjusteEstoqueTabelaView.as_view(), name="ajuste_tabela"),
    path("ajustes/novo/", views.AjusteEstoqueCreateView.as_view(), name="ajuste_novo"),
]
