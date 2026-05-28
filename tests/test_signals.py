from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from apps.cardapio.models import HistoricoPreco, Prato
from apps.estoque.models import EntradaEstoque
from apps.pedidos.models import ItemPedido, Pedido

pytestmark = pytest.mark.django_db


def _entrada(ingrediente, qtd, custo, user=None):
    return EntradaEstoque.objects.create(
        restaurante=ingrediente.restaurante,
        ingrediente=ingrediente,
        quantidade=Decimal(qtd),
        custo_unitario=Decimal(custo),
        data_entrada=date.today(),
        usuario=user,
    )


def test_cmp_primeira_entrada(ingrediente):
    _entrada(ingrediente, "1000", "0.0200")
    ingrediente.refresh_from_db()
    assert ingrediente.estoque_atual == Decimal("1000.000")
    assert ingrediente.custo_unitario == Decimal("0.0200")


def test_cmp_media_ponderada(ingrediente):
    # 1000g @ 0.02 + 1000g @ 0.04 => média 0.03
    _entrada(ingrediente, "1000", "0.0200")
    _entrada(ingrediente, "1000", "0.0400")
    ingrediente.refresh_from_db()
    assert ingrediente.estoque_atual == Decimal("2000.000")
    assert ingrediente.custo_unitario == Decimal("0.0300")


def test_cascata_custo_ficha_e_prato(prato, ingrediente):
    # ficha usa 200g; custo 0.02/g => custo_total 4.00, custo_porcao 4.00 (rend=1)
    _entrada(ingrediente, "1000", "0.0200")
    prato.ficha.refresh_from_db()
    prato.refresh_from_db()
    assert prato.ficha.custo_total == Decimal("4.0000")
    assert prato.ficha.custo_porcao == Decimal("4.0000")
    assert prato.custo_atual == Decimal("4.0000")
    # margem = (30 - 4)/30*100 = 86.67
    assert prato.margem_lucro == Decimal("86.67")


def test_margem_alerta_emitido(prato, ingrediente, monkeypatch):
    eventos = []
    monkeypatch.setattr(
        "apps.fichas.signals.notify",
        lambda rid, ev, payload: eventos.append((ev, payload)),
    )
    # custo alto deixa margem abaixo da padrão (60%)
    _entrada(ingrediente, "1000", "0.1000")  # 200g*0.1 = 20 => margem (30-20)/30=33%
    prato.refresh_from_db()
    assert prato.margem_lucro < Decimal("60")
    assert any(ev == "margem_alerta" for ev, _ in eventos)


def test_baixa_estoque_e_alertas(prato, ingrediente, user, monkeypatch):
    eventos = []
    monkeypatch.setattr(
        "apps.pedidos.signals.notify",
        lambda rid, ev, payload: eventos.append(ev),
    )
    # estoque inicial 600g (minimo 500); pedido consome 200g*3 = 600 => chega a 0
    _entrada(ingrediente, "600", "0.0200")
    ingrediente.refresh_from_db()
    assert ingrediente.estoque_atual == Decimal("600.000")

    pedido = Pedido.objects.create(restaurante=prato.restaurante, usuario=user)
    item = ItemPedido.objects.create(pedido=pedido, prato=prato, quantidade=3)
    item.status = ItemPedido.Status.PRONTO
    item.save()

    ingrediente.refresh_from_db()
    prato.refresh_from_db()
    assert ingrediente.estoque_atual == Decimal("0.000")
    assert prato.disponivel is False
    assert "estoque_alerta" in eventos
    assert "prato_indisponivel" in eventos
    assert item.pronto_em is not None


def test_baixa_estoque_idempotente(prato, ingrediente, user):
    _entrada(ingrediente, "1000", "0.0200")
    pedido = Pedido.objects.create(restaurante=prato.restaurante, usuario=user)
    item = ItemPedido.objects.create(pedido=pedido, prato=prato, quantidade=1)
    item.status = ItemPedido.Status.PRONTO
    item.save()
    item.save()  # segundo save não deve baixar de novo
    ingrediente.refresh_from_db()
    assert ingrediente.estoque_atual == Decimal("800.000")  # 1000 - 200, uma vez só


def test_historico_preco_criado(prato, user):
    prato.preco_venda = Decimal("35.00")
    prato._usuario_alteracao = user
    prato.save()
    hist = HistoricoPreco.objects.filter(prato=prato)
    assert hist.count() == 1
    h = hist.first()
    assert h.preco_anterior == Decimal("30.00")
    assert h.preco_novo == Decimal("35.00")
    assert h.usuario == user


def test_historico_preco_nao_criado_sem_mudanca(prato):
    prato.nome = "Hambúrguer Renomeado"
    prato.save()
    assert HistoricoPreco.objects.filter(prato=prato).count() == 0
