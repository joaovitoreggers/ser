from __future__ import annotations

from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.financeiro.models import Pagamento
from apps.pedidos.models import ItemPedido, Pedido

pytestmark = pytest.mark.django_db


def _pedido_pago(restaurante, prato, total="60.00"):
    pedido = Pedido.objects.create(
        restaurante=restaurante,
        tipo=Pedido.Tipo.BALCAO,
        status=Pedido.Status.PAGO,
        fechado_em=timezone.now(),
    )
    ItemPedido(pedido=pedido, prato=prato, quantidade=2).save()
    pedido.recalcular_totais(save=True)
    Pagamento.objects.create(
        pedido=pedido, forma="dinheiro", valor=Decimal(total), usuario=None
    )
    return pedido


# --------------------------------------------------------------------------- #
# RBAC
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("perfil", ["admin", "gerente"])
def test_dashboard_acesso_permitido(client, make_perfil, perfil):
    client.force_login(make_perfil(perfil))
    assert client.get(reverse("relatorios:dashboard")).status_code == 200


@pytest.mark.parametrize("perfil", ["garcom", "cozinheiro", "caixa", "almoxarife"])
def test_dashboard_acesso_negado(client, make_perfil, perfil):
    client.force_login(make_perfil(perfil))
    assert client.get(reverse("relatorios:dashboard")).status_code == 403


def test_dashboard_exige_login(client):
    resp = client.get(reverse("relatorios:dashboard"))
    assert resp.status_code == 302
    assert reverse("usuarios:login") in resp.url


# --------------------------------------------------------------------------- #
# Conteúdo financeiro
# --------------------------------------------------------------------------- #
def test_dashboard_mostra_faturamento_do_dia(client, make_perfil, restaurante, prato):
    _pedido_pago(restaurante, prato, total="60.00")
    client.force_login(make_perfil("gerente"))
    resp = client.get(reverse("relatorios:dashboard"))
    assert resp.status_code == 200
    body = resp.content.decode()
    assert "60,00" in body  # faturamento do dia (locale pt-BR)
    assert "Dinheiro" in body  # recebimentos por forma
