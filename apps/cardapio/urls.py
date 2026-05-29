from __future__ import annotations

from django.urls import path

from . import views

app_name = "cardapio"

urlpatterns = [
    # Pratos (landing do módulo)
    path("", views.PratoListView.as_view(), name="prato_list"),
    path("tabela/", views.PratoTabelaView.as_view(), name="prato_tabela"),
    path("novo/", views.PratoCreateView.as_view(), name="prato_novo"),
    path("<uuid:pk>/editar/", views.PratoUpdateView.as_view(), name="prato_editar"),
    path("<uuid:pk>/excluir/", views.PratoDeleteView.as_view(), name="prato_excluir"),
    # Categorias de prato
    path(
        "categorias/",
        views.CategoriaPratoListView.as_view(),
        name="categoria_list",
    ),
    path(
        "categorias/tabela/",
        views.CategoriaPratoTabelaView.as_view(),
        name="categoria_tabela",
    ),
    path(
        "categorias/nova/",
        views.CategoriaPratoCreateView.as_view(),
        name="categoria_novo",
    ),
    path(
        "categorias/<uuid:pk>/editar/",
        views.CategoriaPratoUpdateView.as_view(),
        name="categoria_editar",
    ),
    path(
        "categorias/<uuid:pk>/excluir/",
        views.CategoriaPratoDeleteView.as_view(),
        name="categoria_excluir",
    ),
]
