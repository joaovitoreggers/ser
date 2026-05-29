from __future__ import annotations

from django.urls import path

from . import views

app_name = "pedidos"

urlpatterns = [
    # Salão / mesas
    path("mesas/", views.MesaBoardView.as_view(), name="mesas"),
    path("mesas/gerenciar/", views.MesaListView.as_view(), name="mesa_list"),
    path("mesas/gerenciar/tabela/", views.MesaTabelaView.as_view(), name="mesa_tabela"),
    path("mesas/gerenciar/nova/", views.MesaCreateView.as_view(), name="mesa_novo"),
    path(
        "mesas/gerenciar/<uuid:pk>/editar/",
        views.MesaUpdateView.as_view(),
        name="mesa_editar",
    ),
    path(
        "mesas/gerenciar/<uuid:pk>/excluir/",
        views.MesaDeleteView.as_view(),
        name="mesa_excluir",
    ),
    path("mesas/<uuid:pk>/abrir/", views.PedidoAbrirView.as_view(), name="pedido_abrir"),
    # Pedidos / comanda
    path("balcao/novo/", views.PedidoBalcaoView.as_view(), name="pedido_balcao"),
    path("<uuid:pk>/", views.PedidoDetailView.as_view(), name="pedido_detalhe"),
    path(
        "<uuid:pk>/itens/adicionar/",
        views.ItemAdicionarView.as_view(),
        name="item_adicionar",
    ),
    path("<uuid:pk>/enviar/", views.PedidoEnviarView.as_view(), name="pedido_enviar"),
    path(
        "itens/<uuid:pk>/cancelar/",
        views.ItemCancelarView.as_view(),
        name="item_cancelar",
    ),
    # KDS / cozinha
    path("kds/", views.KDSView.as_view(), name="kds"),
    path("kds/itens/<uuid:pk>/avancar/", views.ItemAvancarView.as_view(), name="item_avancar"),
    # Caixa
    path("caixa/", views.CaixaView.as_view(), name="caixa"),
    path("caixa/<uuid:pk>/pagar/", views.PedidoPagarView.as_view(), name="pedido_pagar"),
]
