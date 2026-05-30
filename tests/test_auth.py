from __future__ import annotations

import pytest
from django.contrib.auth.models import Group
from django.urls import reverse

pytestmark = pytest.mark.django_db


def test_grupos_rbac_criados_com_permissoes():
    nomes = set(
        Group.objects.values_list("name", flat=True)
    )
    assert {
        "admin",
        "gerente",
        "garcom",
        "cozinheiro",
        "caixa",
        "almoxarife",
    } <= nomes

    garcom = Group.objects.get(name="garcom")
    codenames = set(garcom.permissions.values_list("codename", flat=True))
    assert "add_pedido" in codenames
    assert "view_prato" in codenames
    # garçom não administra estoque
    assert "add_ingrediente" not in codenames

    cozinheiro = Group.objects.get(name="cozinheiro")
    cz = set(cozinheiro.permissions.values_list("codename", flat=True))
    assert "change_itempedido" in cz
    assert "add_itempedido" not in cz  # só altera status


@pytest.mark.parametrize(
    "perfil,destino",
    [
        ("admin", "/"),
        ("gerente", "/"),
        ("garcom", "/pedidos/mesas/"),
        ("cozinheiro", "/pedidos/kds/"),
        ("caixa", "/pedidos/caixa/"),
        ("almoxarife", "/estoque/"),
    ],
)
def test_login_redireciona_por_perfil(client, make_perfil, perfil, destino):
    make_perfil(perfil, senha="senha-forte-123")
    resp = client.post(
        reverse("usuarios:login"),
        {"username": f"{perfil}_user", "password": "senha-forte-123"},
    )
    assert resp.status_code == 302
    assert resp.url == destino


def test_perfil_required_bloqueia_perfil_errado(client, make_perfil):
    make_perfil("garcom", senha="senha-forte-123")
    client.login(username="garcom_user", password="senha-forte-123")
    # garçom não acessa o KDS (cozinheiro/gerente/admin)
    resp = client.get(reverse("pedidos:kds"))
    assert resp.status_code == 403


def test_perfil_required_permite_perfil_certo(client, make_perfil, restaurante):
    make_perfil("cozinheiro", senha="senha-forte-123")
    client.login(username="cozinheiro_user", password="senha-forte-123")
    resp = client.get(reverse("pedidos:kds"))
    assert resp.status_code == 200
    assert "Cozinha" in resp.content.decode()  # página real do KDS


def test_tenant_mixin_exige_login(client):
    resp = client.get(reverse("estoque:home"))
    assert resp.status_code == 302
    assert reverse("usuarios:login") in resp.url


def test_pin_login_valida_hash(client, make_perfil):
    make_perfil("caixa", pin="4321")
    resp = client.post(
        reverse("usuarios:pin_login"),
        {"username": "caixa_user", "pin": "4321"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["redirect"] == "/pedidos/caixa/"


def test_pin_login_rejeita_pin_errado(client, make_perfil):
    make_perfil("caixa", pin="4321")
    resp = client.post(
        reverse("usuarios:pin_login"),
        {"username": "caixa_user", "pin": "0000"},
    )
    assert resp.status_code == 401
    assert resp.json()["ok"] is False
