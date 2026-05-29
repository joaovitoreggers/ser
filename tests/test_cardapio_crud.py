from __future__ import annotations

from decimal import Decimal

import pytest
from django.urls import reverse

from apps.cardapio.models import CategoriaPrato, HistoricoPreco, Prato
from apps.fichas.models import FichaTecnica

pytestmark = pytest.mark.django_db


@pytest.fixture
def gerente(make_perfil):
    return make_perfil("gerente")


@pytest.fixture
def client_gerente(client, gerente):
    client.force_login(gerente)
    return client


# --------------------------------------------------------------------------- #
# Acesso / RBAC
# --------------------------------------------------------------------------- #
def test_lista_renderiza_para_gerente(client_gerente):
    resp = client_gerente.get(reverse("cardapio:prato_list"))
    assert resp.status_code == 200


@pytest.mark.parametrize("perfil", ["garcom", "almoxarife"])
def test_perfil_sem_acesso_recebe_403(client, make_perfil, perfil):
    client.force_login(make_perfil(perfil))
    resp = client.get(reverse("cardapio:prato_list"))
    assert resp.status_code == 403


def test_nao_autenticado_redireciona(client):
    resp = client.get(reverse("cardapio:prato_list"))
    assert resp.status_code == 302
    assert "login" in resp.url


# --------------------------------------------------------------------------- #
# Categorias de prato
# --------------------------------------------------------------------------- #
def test_criar_categoria(client_gerente, restaurante):
    resp = client_gerente.post(
        reverse("cardapio:categoria_novo"), {"nome": "Bebidas", "ordem": "2"}
    )
    assert resp.status_code == 200
    assert resp["HX-Trigger"] == "cardapio:changed"
    cat = CategoriaPrato.objects.get(nome="Bebidas")
    assert cat.restaurante == restaurante
    assert cat.ordem == 2


def test_excluir_categoria_com_prato_e_bloqueada(client_gerente, prato):
    resp = client_gerente.post(
        reverse("cardapio:categoria_excluir", args=[prato.categoria_id])
    )
    assert resp.status_code == 200  # PROTECT -> re-renderiza com erro
    assert "HX-Trigger" not in resp
    assert "Não é possível" in resp.content.decode()
    assert CategoriaPrato.objects.filter(pk=prato.categoria_id).exists()


# --------------------------------------------------------------------------- #
# Pratos: criação + cálculo de margem (§3B)
# --------------------------------------------------------------------------- #
def test_criar_prato_calcula_margem(client_gerente, restaurante, ficha):
    cat = CategoriaPrato.objects.create(restaurante=restaurante, nome="Lanches")
    resp = client_gerente.post(
        reverse("cardapio:prato_novo"),
        {
            "nome": "Burger",
            "categoria": cat.pk,
            "ficha": ficha.pk,
            "preco_venda": "30.00",
            "disponivel": "on",
        },
    )
    assert resp.status_code == 200
    assert resp["HX-Trigger"] == "cardapio:changed"
    prato = Prato.objects.get(nome="Burger")
    assert prato.restaurante == restaurante
    assert prato.custo_atual == ficha.custo_porcao
    # ficha.custo_porcao == 0 -> margem (30 - 0) / 30 * 100 = 100
    assert prato.margem_lucro == Decimal("100.00")


def test_ficha_ja_usada_nao_pode_ser_revinculada(client_gerente, restaurante, prato):
    cat = CategoriaPrato.objects.create(restaurante=restaurante, nome="Outra")
    resp = client_gerente.post(
        reverse("cardapio:prato_novo"),
        {
            "nome": "Duplicado",
            "categoria": cat.pk,
            "ficha": prato.ficha_id,  # já vinculada ao `prato`
            "preco_venda": "20.00",
            "disponivel": "on",
        },
    )
    assert resp.status_code == 200  # form inválido -> re-renderiza
    assert "HX-Trigger" not in resp
    assert not Prato.objects.filter(nome="Duplicado").exists()


# --------------------------------------------------------------------------- #
# Pratos: histórico de preço (§3D)
# --------------------------------------------------------------------------- #
def test_editar_preco_registra_historico(client_gerente, gerente, prato):
    resp = client_gerente.post(
        reverse("cardapio:prato_editar", args=[prato.pk]),
        {
            "nome": prato.nome,
            "categoria": prato.categoria_id,
            "ficha": prato.ficha_id,
            "preco_venda": "35.00",
            "disponivel": "on",
        },
    )
    assert resp.status_code == 200
    assert resp["HX-Trigger"] == "cardapio:changed"
    prato.refresh_from_db()
    assert prato.preco_venda == Decimal("35.00")
    hist = HistoricoPreco.objects.get(prato=prato)
    assert hist.preco_anterior == Decimal("30.00")
    assert hist.preco_novo == Decimal("35.00")
    assert hist.usuario == gerente


def test_editar_sem_mudar_preco_nao_gera_historico(client_gerente, prato):
    client_gerente.post(
        reverse("cardapio:prato_editar", args=[prato.pk]),
        {
            "nome": "Hambúrguer Renomeado",
            "categoria": prato.categoria_id,
            "ficha": prato.ficha_id,
            "preco_venda": "30.00",  # inalterado
            "disponivel": "on",
        },
    )
    prato.refresh_from_db()
    assert prato.nome == "Hambúrguer Renomeado"
    assert not HistoricoPreco.objects.filter(prato=prato).exists()


# --------------------------------------------------------------------------- #
# Exclusão + multi-tenant
# --------------------------------------------------------------------------- #
def test_excluir_prato(client_gerente, prato):
    resp = client_gerente.post(reverse("cardapio:prato_excluir", args=[prato.pk]))
    assert resp.status_code == 200
    assert resp["HX-Trigger"] == "cardapio:changed"
    assert not Prato.objects.filter(pk=prato.pk).exists()


def test_prato_de_outro_tenant(client_gerente, outro_restaurante):
    cat = CategoriaPrato.objects.create(restaurante=outro_restaurante, nome="X")
    ficha = FichaTecnica.objects.create(
        restaurante=outro_restaurante, nome="FichaAlheia", rendimento=1
    )
    alheio = Prato.objects.create(
        restaurante=outro_restaurante,
        ficha=ficha,
        categoria=cat,
        nome="PratoAlheio",
        preco_venda=Decimal("10.00"),
    )
    resp = client_gerente.get(reverse("cardapio:prato_list"))
    assert b"PratoAlheio" not in resp.content
    resp = client_gerente.get(reverse("cardapio:prato_editar", args=[alheio.pk]))
    assert resp.status_code == 404
