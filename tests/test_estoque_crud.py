from __future__ import annotations

from decimal import Decimal

import pytest
from django.urls import reverse

from apps.estoque.models import (
    AjusteEstoque,
    CategoriaIngrediente,
    EntradaEstoque,
    Fornecedor,
    Ingrediente,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def almoxarife(make_perfil):
    return make_perfil("almoxarife")


@pytest.fixture
def client_almoxarife(client, almoxarife):
    client.force_login(almoxarife)
    return client


# --------------------------------------------------------------------------- #
# Render / acesso
# --------------------------------------------------------------------------- #
def test_listas_renderizam(client_almoxarife):
    for nome in (
        "home",
        "categoria_list",
        "fornecedor_list",
        "entrada_list",
        "ajuste_list",
    ):
        resp = client_almoxarife.get(reverse(f"estoque:{nome}"))
        assert resp.status_code == 200


def test_perfil_sem_acesso_recebe_403(client, make_perfil):
    garcom = make_perfil("garcom")
    client.force_login(garcom)
    resp = client.get(reverse("estoque:home"))
    assert resp.status_code == 403


def test_nao_autenticado_redireciona_login(client):
    resp = client.get(reverse("estoque:home"))
    assert resp.status_code == 302
    assert "/login" in resp.url or "login" in resp.url


# --------------------------------------------------------------------------- #
# Ingrediente / Fornecedor CRUD
# --------------------------------------------------------------------------- #
def test_criar_ingrediente(client_almoxarife, restaurante):
    resp = client_almoxarife.post(
        reverse("estoque:ingrediente_novo"),
        {
            "nome": "Tomate",
            "unidade_medida": "kg",
            "estoque_minimo": "2",
            "custo_unitario": "5",
            "ativo": "on",
        },
    )
    assert resp.status_code == 200
    assert resp["HX-Trigger"] == "estoque:changed"
    ing = Ingrediente.objects.get(nome="Tomate")
    assert ing.restaurante == restaurante


def test_criar_categoria(client_almoxarife, restaurante):
    resp = client_almoxarife.post(
        reverse("estoque:categoria_novo"), {"nome": "Laticínios"}
    )
    assert resp.status_code == 200
    assert resp["HX-Trigger"] == "estoque:changed"
    assert CategoriaIngrediente.objects.filter(
        nome="Laticínios", restaurante=restaurante
    ).exists()


def test_categoria_duplicada_rejeitada(client_almoxarife, restaurante):
    CategoriaIngrediente.objects.create(restaurante=restaurante, nome="Bebidas")
    resp = client_almoxarife.post(
        reverse("estoque:categoria_novo"), {"nome": "bebidas"}
    )
    # Form inválido re-renderiza o modal (200) sem HX-Trigger e sem criar duplicata.
    assert resp.status_code == 200
    assert "HX-Trigger" not in resp
    assert b"J\xc3\xa1 existe uma categoria" in resp.content
    assert CategoriaIngrediente.objects.filter(restaurante=restaurante).count() == 1


def test_editar_categoria(client_almoxarife, restaurante):
    cat = CategoriaIngrediente.objects.create(restaurante=restaurante, nome="Carnes")
    resp = client_almoxarife.post(
        reverse("estoque:categoria_editar", args=[cat.pk]), {"nome": "Proteínas"}
    )
    assert resp.status_code == 200
    cat.refresh_from_db()
    assert cat.nome == "Proteínas"


def test_excluir_categoria_desvincula_ingrediente(
    client_almoxarife, restaurante, ingrediente
):
    cat = CategoriaIngrediente.objects.create(restaurante=restaurante, nome="Temp")
    ingrediente.categoria = cat
    ingrediente.save(update_fields=["categoria"])
    resp = client_almoxarife.post(reverse("estoque:categoria_excluir", args=[cat.pk]))
    assert resp.status_code == 200
    assert not CategoriaIngrediente.objects.filter(pk=cat.pk).exists()
    ingrediente.refresh_from_db()
    assert ingrediente.categoria_id is None


def test_categoria_de_outro_tenant_nao_aparece(client_almoxarife, outro_restaurante):
    CategoriaIngrediente.objects.create(
        restaurante=outro_restaurante, nome="CategoriaSecreta"
    )
    resp = client_almoxarife.get(reverse("estoque:categoria_tabela"))
    assert b"CategoriaSecreta" not in resp.content


def test_criar_fornecedor(client_almoxarife, restaurante):
    resp = client_almoxarife.post(
        reverse("estoque:fornecedor_novo"),
        {"nome": "Distribuidora X", "cnpj": "33.333.333/0001-33", "ativo": "on"},
    )
    assert resp.status_code == 200
    assert Fornecedor.objects.filter(
        nome="Distribuidora X", restaurante=restaurante
    ).exists()


def test_ingrediente_de_outro_tenant_nao_aparece(
    client_almoxarife, outro_restaurante
):
    Ingrediente.objects.create(
        restaurante=outro_restaurante, nome="Secreto", unidade_medida="un"
    )
    resp = client_almoxarife.get(reverse("estoque:ingrediente_tabela"))
    assert b"Secreto" not in resp.content


# --------------------------------------------------------------------------- #
# Entrada → signal CMP atualiza estoque/custo e grava usuario
# --------------------------------------------------------------------------- #
def test_criar_entrada_atualiza_estoque_e_usuario(
    client_almoxarife, almoxarife, ingrediente
):
    resp = client_almoxarife.post(
        reverse("estoque:entrada_nova"),
        {
            "ingrediente": str(ingrediente.pk),
            "quantidade": "1000",
            "custo_unitario": "0.02",
            "data_entrada": "2026-05-28",
            "nota_fiscal": "NF-1",
        },
    )
    assert resp.status_code == 200
    entrada = EntradaEstoque.objects.get(ingrediente=ingrediente)
    assert entrada.usuario == almoxarife
    ingrediente.refresh_from_db()
    assert ingrediente.estoque_atual == Decimal("1000.000")
    assert ingrediente.custo_unitario == Decimal("0.0200")


# --------------------------------------------------------------------------- #
# Ajuste → captura qtd_anterior, aplica qtd_nova ao estoque, grava usuario
# --------------------------------------------------------------------------- #
def test_criar_ajuste_aplica_ao_estoque(client_almoxarife, almoxarife, ingrediente):
    ingrediente.estoque_atual = Decimal("100")
    ingrediente.save(update_fields=["estoque_atual"])

    resp = client_almoxarife.post(
        reverse("estoque:ajuste_novo"),
        {
            "ingrediente": str(ingrediente.pk),
            "qtd_nova": "80",
            "motivo": "inventario",
            "descricao": "Contagem mensal",
        },
    )
    assert resp.status_code == 200
    ajuste = AjusteEstoque.objects.get(ingrediente=ingrediente)
    assert ajuste.qtd_anterior == Decimal("100.000")
    assert ajuste.qtd_nova == Decimal("80.000")
    assert ajuste.usuario == almoxarife
    ingrediente.refresh_from_db()
    assert ingrediente.estoque_atual == Decimal("80.000")
