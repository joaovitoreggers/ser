from __future__ import annotations

from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from apps.pedidos.models import ItemPedido, Pedido

pytestmark = pytest.mark.django_db


def test_itempedido_snapshot_congelado(prato, user):
    pedido = Pedido.objects.create(restaurante=prato.restaurante, usuario=user)
    item = ItemPedido.objects.create(pedido=pedido, prato=prato, quantidade=2)
    assert item.preco_unitario == Decimal("30.00")
    assert item.subtotal == Decimal("60.00")

    # alterar o preço do prato não recalcula o snapshot do item
    prato.preco_venda = Decimal("99.00")
    prato.save()
    item.refresh_from_db()
    assert item.preco_unitario == Decimal("30.00")


def test_pedido_recalcular_totais_servidor(prato, user):
    pedido = Pedido.objects.create(
        restaurante=prato.restaurante, usuario=user, desconto=Decimal("10.00")
    )
    ItemPedido.objects.create(pedido=pedido, prato=prato, quantidade=2)  # 60
    ItemPedido.objects.create(pedido=pedido, prato=prato, quantidade=1)  # 30
    pedido.recalcular_totais()
    assert pedido.subtotal == Decimal("90.00")
    assert pedido.total == Decimal("80.00")


def test_pedido_pago_bloqueia_item(prato, user):
    pedido = Pedido.objects.create(restaurante=prato.restaurante, usuario=user)
    item = ItemPedido.objects.create(pedido=pedido, prato=prato, quantidade=1)
    pedido.status = Pedido.Status.PAGO
    pedido.save()

    item.quantidade = 5
    with pytest.raises(ValidationError):
        item.full_clean()


def test_totais_ignoram_itens_cancelados(prato, user):
    pedido = Pedido.objects.create(restaurante=prato.restaurante, usuario=user)
    ItemPedido.objects.create(pedido=pedido, prato=prato, quantidade=2)
    cancelado = ItemPedido.objects.create(pedido=pedido, prato=prato, quantidade=1)
    cancelado.status = ItemPedido.Status.CANCELADO
    cancelado.save()
    pedido.recalcular_totais()
    assert pedido.subtotal == Decimal("60.00")
