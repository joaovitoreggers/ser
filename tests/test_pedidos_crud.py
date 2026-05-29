from __future__ import annotations

from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.core.models import LogAuditoria
from apps.pedidos.models import ItemPedido, Mesa, Pedido

pytestmark = pytest.mark.django_db


@pytest.fixture
def garcom(make_perfil):
    return make_perfil("garcom")


@pytest.fixture
def client_garcom(client, garcom):
    client.force_login(garcom)
    return client


@pytest.fixture
def mesa(restaurante):
    return Mesa.objects.create(restaurante=restaurante, numero=1)


def _pedido(restaurante, mesa=None, status=Pedido.Status.ABERTO):
    return Pedido.objects.create(
        restaurante=restaurante, mesa=mesa, tipo=Pedido.Tipo.MESA if mesa else Pedido.Tipo.BALCAO, status=status
    )


def _item(pedido, prato, quantidade=1, status=ItemPedido.Status.AGUARDANDO):
    item = ItemPedido(pedido=pedido, prato=prato, quantidade=quantidade)
    item.status = status
    if status != ItemPedido.Status.AGUARDANDO:
        item.enviado_em = timezone.now()
    item.save()
    return item


# --------------------------------------------------------------------------- #
# RBAC (§5)
# --------------------------------------------------------------------------- #
def test_garcom_acessa_mesas(client_garcom):
    assert client_garcom.get(reverse("pedidos:mesas")).status_code == 200


@pytest.mark.parametrize("perfil", ["cozinheiro", "caixa", "almoxarife"])
def test_perfil_sem_acesso_mesas_403(client, make_perfil, perfil):
    client.force_login(make_perfil(perfil))
    assert client.get(reverse("pedidos:mesas")).status_code == 403


def test_cozinheiro_acessa_kds(client, make_perfil):
    client.force_login(make_perfil("cozinheiro"))
    assert client.get(reverse("pedidos:kds")).status_code == 200


def test_garcom_nao_acessa_kds(client_garcom):
    assert client_garcom.get(reverse("pedidos:kds")).status_code == 403


def test_caixa_acessa_caixa(client, make_perfil):
    client.force_login(make_perfil("caixa"))
    assert client.get(reverse("pedidos:caixa")).status_code == 200


def test_garcom_nao_gerencia_mesas(client_garcom):
    assert client_garcom.get(reverse("pedidos:mesa_list")).status_code == 403


def test_nao_autenticado_redireciona(client):
    resp = client.get(reverse("pedidos:mesas"))
    assert resp.status_code == 302
    assert "login" in resp.url


# --------------------------------------------------------------------------- #
# Mesas CRUD
# --------------------------------------------------------------------------- #
def test_gerente_cria_mesa(client, make_perfil, restaurante):
    client.force_login(make_perfil("gerente"))
    resp = client.post(reverse("pedidos:mesa_novo"), {"numero": "5", "status": "livre"})
    assert resp.status_code == 200
    assert resp["HX-Trigger"] == "pedidos:changed"
    assert Mesa.objects.filter(restaurante=restaurante, numero=5).exists()


def test_mesa_numero_unico_por_tenant(client, make_perfil, restaurante, mesa):
    client.force_login(make_perfil("gerente"))
    resp = client.post(reverse("pedidos:mesa_novo"), {"numero": "1", "status": "livre"})
    assert resp.status_code == 200
    assert "HX-Trigger" not in resp
    assert Mesa.objects.filter(restaurante=restaurante, numero=1).count() == 1


# --------------------------------------------------------------------------- #
# Abertura de pedido
# --------------------------------------------------------------------------- #
def test_abrir_pedido_para_mesa(client_garcom, restaurante, mesa):
    resp = client_garcom.post(reverse("pedidos:pedido_abrir", args=[mesa.pk]))
    assert resp.status_code == 302
    pedido = Pedido.objects.get(mesa=mesa)
    assert pedido.status == Pedido.Status.ABERTO
    mesa.refresh_from_db()
    assert mesa.status == Mesa.Status.OCUPADA
    assert resp.url == reverse("pedidos:pedido_detalhe", args=[pedido.pk])


def test_abrir_pedido_reaproveita_comanda(client_garcom, restaurante, mesa):
    client_garcom.post(reverse("pedidos:pedido_abrir", args=[mesa.pk]))
    client_garcom.post(reverse("pedidos:pedido_abrir", args=[mesa.pk]))
    assert Pedido.objects.filter(mesa=mesa).count() == 1


# --------------------------------------------------------------------------- #
# Itens: snapshot (§4.2) + imutabilidade pós-pago (§4.1)
# --------------------------------------------------------------------------- #
def test_adicionar_item_congela_preco_e_recalcula(client_garcom, restaurante, mesa, prato):
    pedido = _pedido(restaurante, mesa)
    resp = client_garcom.post(
        reverse("pedidos:item_adicionar", args=[pedido.pk]),
        {"prato": prato.pk, "quantidade": "2"},
    )
    assert resp.status_code == 302
    item = pedido.itens.get()
    assert item.preco_unitario == Decimal("30.00")  # snapshot do prato
    assert item.subtotal == Decimal("60.00")
    pedido.refresh_from_db()
    assert pedido.subtotal == Decimal("60.00")
    assert pedido.total == Decimal("60.00")


def test_adicionar_item_em_pedido_pago_bloqueado(client_garcom, restaurante, mesa, prato):
    pedido = _pedido(restaurante, mesa, status=Pedido.Status.PAGO)
    resp = client_garcom.post(
        reverse("pedidos:item_adicionar", args=[pedido.pk]),
        {"prato": prato.pk, "quantidade": "1"},
    )
    assert resp.status_code == 409
    assert not pedido.itens.exists()


# --------------------------------------------------------------------------- #
# Envio à cozinha
# --------------------------------------------------------------------------- #
def test_enviar_a_cozinha(client_garcom, restaurante, mesa, prato):
    pedido = _pedido(restaurante, mesa)
    _item(pedido, prato)
    resp = client_garcom.post(reverse("pedidos:pedido_enviar", args=[pedido.pk]))
    assert resp.status_code == 302
    item = pedido.itens.get()
    assert item.status == ItemPedido.Status.EM_PREPARO
    assert item.enviado_em is not None
    pedido.refresh_from_db()
    assert pedido.status == Pedido.Status.EM_ATENDIMENTO
    mesa.refresh_from_db()
    assert mesa.status == Mesa.Status.EM_ATENDIMENTO


# --------------------------------------------------------------------------- #
# Cancelamento (§4.4)
# --------------------------------------------------------------------------- #
def test_cancelar_item_aguardando_livre(client_garcom, restaurante, mesa, prato):
    pedido = _pedido(restaurante, mesa)
    item = _item(pedido, prato, quantidade=2)
    resp = client_garcom.post(
        reverse("pedidos:item_cancelar", args=[item.pk]), {"motivo": "Cliente desistiu"}
    )
    assert resp.status_code == 302
    item.refresh_from_db()
    assert item.status == ItemPedido.Status.CANCELADO
    assert item.motivo_cancelamento == "Cliente desistiu"
    pedido.refresh_from_db()
    assert pedido.subtotal == Decimal("0")  # item cancelado não conta
    assert LogAuditoria.objects.filter(acao="cancelar_item", entidade_id=item.id).exists()


def test_cancelar_item_em_preparo_sem_pin_bloqueado(client_garcom, restaurante, mesa, prato):
    pedido = _pedido(restaurante, mesa)
    item = _item(pedido, prato, status=ItemPedido.Status.EM_PREPARO)
    resp = client_garcom.post(
        reverse("pedidos:item_cancelar", args=[item.pk]), {"motivo": "Erro", "pin": ""}
    )
    assert resp.status_code == 200  # re-renderiza com erro
    item.refresh_from_db()
    assert item.status == ItemPedido.Status.EM_PREPARO
    assert not LogAuditoria.objects.filter(entidade_id=item.id).exists()


def test_cancelar_item_em_preparo_com_pin_valido(client_garcom, make_perfil, restaurante, mesa, prato):
    make_perfil("gerente", pin="1234")  # aprovador no mesmo tenant
    pedido = _pedido(restaurante, mesa)
    item = _item(pedido, prato, status=ItemPedido.Status.EM_PREPARO)
    resp = client_garcom.post(
        reverse("pedidos:item_cancelar", args=[item.pk]),
        {"motivo": "Item errado", "pin": "1234"},
    )
    assert resp.status_code == 302
    item.refresh_from_db()
    assert item.status == ItemPedido.Status.CANCELADO
    log = LogAuditoria.objects.get(acao="cancelar_item", entidade_id=item.id)
    assert "gerente" in (log.dados_depois.get("aprovador") or "").lower()


# --------------------------------------------------------------------------- #
# KDS: avanço de status + baixa de estoque (§3C)
# --------------------------------------------------------------------------- #
def test_kds_marcar_pronto_baixa_estoque(client, make_perfil, restaurante, prato, ingrediente):
    ingrediente.estoque_atual = Decimal("1000")
    ingrediente.save(update_fields=["estoque_atual"])
    client.force_login(make_perfil("cozinheiro"))
    pedido = _pedido(restaurante)
    item = _item(pedido, prato, quantidade=1, status=ItemPedido.Status.EM_PREPARO)

    resp = client.post(reverse("pedidos:item_avancar", args=[item.pk]))
    assert resp.status_code == 302
    item.refresh_from_db()
    assert item.status == ItemPedido.Status.PRONTO
    ingrediente.refresh_from_db()
    # ficha principal: 200 por porção × 1 → baixa de 200
    assert ingrediente.estoque_atual == Decimal("800")


def test_kds_pronto_para_entregue(client, make_perfil, restaurante, prato):
    client.force_login(make_perfil("cozinheiro"))
    pedido = _pedido(restaurante)
    item = _item(pedido, prato, status=ItemPedido.Status.PRONTO)
    resp = client.post(reverse("pedidos:item_avancar", args=[item.pk]))
    assert resp.status_code == 302
    item.refresh_from_db()
    assert item.status == ItemPedido.Status.ENTREGUE


# --------------------------------------------------------------------------- #
# Caixa: fechamento (§4.3)
# --------------------------------------------------------------------------- #
def test_pagar_valor_insuficiente_bloqueado(client, make_perfil, restaurante, mesa, prato):
    client.force_login(make_perfil("caixa"))
    pedido = _pedido(restaurante, mesa)
    _item(pedido, prato, quantidade=2)  # total 60
    resp = client.post(
        reverse("pedidos:pedido_pagar", args=[pedido.pk]),
        {"desconto": "0", "valor_pago": "50"},
    )
    assert resp.status_code == 200
    pedido.refresh_from_db()
    assert pedido.status != Pedido.Status.PAGO


def test_pagar_fecha_pedido_e_libera_mesa(client, make_perfil, restaurante, mesa, prato):
    mesa.status = Mesa.Status.OCUPADA
    mesa.save(update_fields=["status"])
    client.force_login(make_perfil("caixa"))
    pedido = _pedido(restaurante, mesa)
    _item(pedido, prato, quantidade=2)  # total 60
    resp = client.post(
        reverse("pedidos:pedido_pagar", args=[pedido.pk]),
        {"desconto": "0", "valor_pago": "60"},
    )
    assert resp.status_code == 302
    pedido.refresh_from_db()
    assert pedido.status == Pedido.Status.PAGO
    assert pedido.fechado_em is not None
    mesa.refresh_from_db()
    assert mesa.status == Mesa.Status.LIVRE
    assert LogAuditoria.objects.filter(acao="fechar_pedido", entidade_id=pedido.id).exists()


def test_pagar_com_desconto(client, make_perfil, restaurante, mesa, prato):
    client.force_login(make_perfil("caixa"))
    pedido = _pedido(restaurante, mesa)
    _item(pedido, prato, quantidade=2)  # subtotal 60
    resp = client.post(
        reverse("pedidos:pedido_pagar", args=[pedido.pk]),
        {"desconto": "10", "valor_pago": "50"},  # total = 60 - 10 = 50
    )
    assert resp.status_code == 302
    pedido.refresh_from_db()
    assert pedido.status == Pedido.Status.PAGO
    assert pedido.total == Decimal("50.00")


# --------------------------------------------------------------------------- #
# Multi-tenant
# --------------------------------------------------------------------------- #
def test_pedido_de_outro_tenant(client_garcom, outro_restaurante):
    pedido = _pedido(outro_restaurante)
    resp = client_garcom.get(reverse("pedidos:pedido_detalhe", args=[pedido.pk]))
    assert resp.status_code == 404
