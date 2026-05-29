from __future__ import annotations

from decimal import Decimal

import pytest
from django.urls import reverse

from apps.core.models import LogAuditoria
from apps.financeiro.models import MovimentacaoCaixa, Pagamento, TurnoCaixa
from apps.financeiro.services import get_turno_aberto, resumo_turno
from apps.pedidos.models import ItemPedido, Mesa, Pedido

pytestmark = pytest.mark.django_db


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
@pytest.fixture
def mesa(restaurante):
    return Mesa.objects.create(restaurante=restaurante, numero=1)


def _turno(restaurante, usuario=None, abertura="100.00"):
    return TurnoCaixa.objects.create(
        restaurante=restaurante,
        usuario=usuario,
        valor_abertura=Decimal(abertura),
        status=TurnoCaixa.Status.ABERTO,
    )


def _pedido_com_item(restaurante, prato, mesa=None, status=Pedido.Status.AGUARDANDO_PAGAMENTO):
    pedido = Pedido.objects.create(
        restaurante=restaurante,
        mesa=mesa,
        tipo=Pedido.Tipo.MESA if mesa else Pedido.Tipo.BALCAO,
        status=status,
    )
    ItemPedido(pedido=pedido, prato=prato, quantidade=2).save()  # snapshot 30 x2 = 60
    pedido.recalcular_totais(save=True)
    return pedido


# --------------------------------------------------------------------------- #
# RBAC (§5)
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("perfil", ["caixa", "gerente", "admin"])
def test_financeiro_acesso_permitido(client, make_perfil, perfil):
    client.force_login(make_perfil(perfil))
    assert client.get(reverse("financeiro:home")).status_code == 200


@pytest.mark.parametrize("perfil", ["garcom", "cozinheiro", "almoxarife"])
def test_financeiro_acesso_negado(client, make_perfil, perfil):
    client.force_login(make_perfil(perfil))
    assert client.get(reverse("financeiro:home")).status_code == 403


def test_financeiro_exige_login(client):
    resp = client.get(reverse("financeiro:home"))
    assert resp.status_code == 302
    assert reverse("usuarios:login") in resp.url


# --------------------------------------------------------------------------- #
# Abertura / unicidade de turno
# --------------------------------------------------------------------------- #
def test_abrir_turno_cria_turno_aberto(client, make_perfil, restaurante):
    client.force_login(make_perfil("caixa"))
    resp = client.post(reverse("financeiro:turno_abrir"), {"valor_abertura": "150.00"})
    assert resp.status_code == 200  # _trigger_response
    assert resp["HX-Trigger"] == "financeiro:changed"
    turno = get_turno_aberto(restaurante)
    assert turno is not None
    assert turno.valor_abertura == Decimal("150.00")
    assert LogAuditoria.objects.filter(acao="abrir_turno").exists()


def test_abrir_segundo_turno_bloqueado(client, make_perfil, restaurante):
    client.force_login(make_perfil("caixa"))
    _turno(restaurante)
    resp = client.post(reverse("financeiro:turno_abrir"), {"valor_abertura": "50.00"})
    assert resp.status_code == 409
    assert TurnoCaixa.objects.filter(status=TurnoCaixa.Status.ABERTO).count() == 1


# --------------------------------------------------------------------------- #
# Pagamento integrado ao fechamento de pedido
# --------------------------------------------------------------------------- #
def test_pagar_pedido_registra_pagamento_dinheiro(client, make_perfil, restaurante, prato):
    client.force_login(make_perfil("caixa"))
    pedido = _pedido_com_item(restaurante, prato)
    resp = client.post(
        reverse("pedidos:pedido_pagar", args=[pedido.pk]),
        {"desconto": "0", "valor_pago": "100"},  # sem 'forma' -> dinheiro
    )
    assert resp.status_code == 302
    pag = Pagamento.objects.get(pedido=pedido)
    assert pag.forma == "dinheiro"
    assert pag.valor == Decimal("60.00")
    assert pag.troco == Decimal("40.00")


def test_pagar_pedido_forma_pix_sem_troco(client, make_perfil, restaurante, prato):
    client.force_login(make_perfil("caixa"))
    pedido = _pedido_com_item(restaurante, prato)
    client.post(
        reverse("pedidos:pedido_pagar", args=[pedido.pk]),
        {"forma": "pix", "desconto": "0", "valor_pago": "60"},
    )
    pag = Pagamento.objects.get(pedido=pedido)
    assert pag.forma == "pix"
    assert pag.troco == Decimal("0")


# --------------------------------------------------------------------------- #
# Movimentações (sangria/suprimento)
# --------------------------------------------------------------------------- #
def test_suprimento_livre(client, make_perfil, restaurante):
    client.force_login(make_perfil("caixa"))
    _turno(restaurante)
    resp = client.post(
        reverse("financeiro:mov_nova"),
        {"tipo": "suprimento", "valor": "50.00", "motivo": "troco inicial"},
    )
    assert resp.status_code == 200
    mov = MovimentacaoCaixa.objects.get()
    assert mov.tipo == "suprimento"
    assert mov.autorizado_por is None


def test_sangria_sem_pin_rejeitada(client, make_perfil, restaurante):
    client.force_login(make_perfil("caixa"))
    _turno(restaurante)
    resp = client.post(
        reverse("financeiro:mov_nova"),
        {"tipo": "sangria", "valor": "30.00", "motivo": "retirada"},
    )
    assert resp.status_code == 200  # re-render com erro
    assert b"PIN" in resp.content
    assert not MovimentacaoCaixa.objects.exists()


def test_sangria_com_pin_valido(client, make_perfil, restaurante):
    gerente = make_perfil("gerente", pin="9999")
    client.force_login(make_perfil("caixa"))
    _turno(restaurante)
    resp = client.post(
        reverse("financeiro:mov_nova"),
        {"tipo": "sangria", "valor": "30.00", "motivo": "retirada", "pin": "9999"},
    )
    assert resp.status_code == 200
    assert resp["HX-Trigger"] == "financeiro:changed"
    mov = MovimentacaoCaixa.objects.get()
    assert mov.tipo == "sangria"
    assert mov.autorizado_por == gerente


def test_movimentacao_sem_turno_aberto_bloqueada(client, make_perfil):
    client.force_login(make_perfil("caixa"))
    resp = client.post(
        reverse("financeiro:mov_nova"),
        {"tipo": "suprimento", "valor": "10.00", "motivo": "x"},
    )
    assert resp.status_code == 409


# --------------------------------------------------------------------------- #
# Resumo e fechamento
# --------------------------------------------------------------------------- #
def test_resumo_turno_calcula_saldo_esperado(client, make_perfil, restaurante, prato):
    caixa = make_perfil("caixa")
    client.force_login(caixa)
    turno = _turno(restaurante, usuario=caixa, abertura="100.00")
    # paga um pedido em dinheiro (R$ 60)
    pedido = _pedido_com_item(restaurante, prato)
    client.post(
        reverse("pedidos:pedido_pagar", args=[pedido.pk]),
        {"forma": "dinheiro", "desconto": "0", "valor_pago": "60"},
    )
    # suprimento +20, sangria -30
    MovimentacaoCaixa.objects.create(
        turno=turno, tipo="suprimento", valor=Decimal("20.00"), usuario=caixa
    )
    MovimentacaoCaixa.objects.create(
        turno=turno, tipo="sangria", valor=Decimal("30.00"), usuario=caixa
    )
    resumo = resumo_turno(turno)
    assert resumo["dinheiro"] == Decimal("60.00")
    # 100 (abertura) + 60 (dinheiro) + 20 (suprimento) - 30 (sangria) = 150
    assert resumo["saldo_esperado"] == Decimal("150.00")


def test_fechar_turno_define_fechamento(client, make_perfil, restaurante):
    caixa = make_perfil("caixa")
    client.force_login(caixa)
    turno = _turno(restaurante, usuario=caixa, abertura="100.00")
    resp = client.post(
        reverse("financeiro:turno_fechar"), {"valor_fechamento": "100.00"}
    )
    assert resp.status_code == 200
    assert resp["HX-Trigger"] == "financeiro:changed"
    turno.refresh_from_db()
    assert turno.status == TurnoCaixa.Status.FECHADO
    assert turno.valor_fechamento == Decimal("100.00")
    assert turno.fechado_em is not None
    assert LogAuditoria.objects.filter(acao="fechar_turno").exists()


# --------------------------------------------------------------------------- #
# Histórico de turnos e recibo
# --------------------------------------------------------------------------- #
def test_turno_list_acessivel(client, make_perfil, restaurante):
    client.force_login(make_perfil("caixa"))
    _turno(restaurante)
    resp = client.get(reverse("financeiro:turno_list"))
    assert resp.status_code == 200
    assert b"Hist" in resp.content  # "Histórico de turnos"


def test_turno_list_negado_para_garcom(client, make_perfil):
    client.force_login(make_perfil("garcom"))
    assert client.get(reverse("financeiro:turno_list")).status_code == 403


def test_turno_detalhe_lista_pagamentos(client, make_perfil, restaurante, prato):
    caixa = make_perfil("caixa")
    client.force_login(caixa)
    turno = _turno(restaurante, usuario=caixa)
    pedido = _pedido_com_item(restaurante, prato)
    client.post(
        reverse("pedidos:pedido_pagar", args=[pedido.pk]),
        {"forma": "dinheiro", "desconto": "0", "valor_pago": "60"},
    )
    resp = client.get(reverse("financeiro:turno_detalhe", args=[turno.pk]))
    assert resp.status_code == 200
    assert b"recibo" in resp.content


def test_recibo_mostra_pagamento(client, make_perfil, restaurante, prato):
    client.force_login(make_perfil("caixa"))
    pedido = _pedido_com_item(restaurante, prato)
    client.post(
        reverse("pedidos:pedido_pagar", args=[pedido.pk]),
        {"forma": "pix", "desconto": "0", "valor_pago": "60"},
    )
    resp = client.get(reverse("financeiro:recibo", args=[pedido.pk]))
    assert resp.status_code == 200
    body = resp.content.decode()
    assert "Comprovante" in body
    assert "Pix" in body


def test_recibo_isolado_por_tenant(client, make_perfil, outro_restaurante):
    # pedido em outro tenant não é acessível
    pedido = Pedido.objects.create(
        restaurante=outro_restaurante, tipo=Pedido.Tipo.BALCAO
    )
    client.force_login(make_perfil("caixa"))
    assert client.get(reverse("financeiro:recibo", args=[pedido.pk])).status_code == 404


# --------------------------------------------------------------------------- #
# Multi-tenant
# --------------------------------------------------------------------------- #
def test_turno_isolado_por_tenant(client, make_perfil, restaurante, outro_restaurante):
    _turno(outro_restaurante, abertura="999.00")
    client.force_login(make_perfil("caixa"))
    # o turno do outro restaurante não é visível para este tenant
    assert get_turno_aberto(restaurante) is None
    resp = client.get(reverse("financeiro:home"))
    assert resp.status_code == 200
    assert b"Nenhum turno de caixa aberto" in resp.content
