from __future__ import annotations

from decimal import Decimal

import pytest
from django.urls import reverse

from apps.estoque.models import Ingrediente, UnidadeMedida
from apps.fichas.models import FichaIngrediente, FichaTecnica

pytestmark = pytest.mark.django_db


@pytest.fixture
def gerente(make_perfil):
    return make_perfil("gerente")


@pytest.fixture
def client_gerente(client, gerente):
    client.force_login(gerente)
    return client


@pytest.fixture
def ing_carne(restaurante):
    return Ingrediente.objects.create(
        restaurante=restaurante,
        nome="Carne",
        unidade_medida=UnidadeMedida.GRAMA,
        custo_unitario=Decimal("0.05"),
    )


def _ficha_post(nome, rendimento, linhas, *, initial=0):
    data = {
        "nome": nome,
        "rendimento": str(rendimento),
        "ativo": "on",
        "ingredientes-TOTAL_FORMS": str(len(linhas)),
        "ingredientes-INITIAL_FORMS": str(initial),
        "ingredientes-MIN_NUM_FORMS": "1",
        "ingredientes-MAX_NUM_FORMS": "1000",
    }
    for i, linha in enumerate(linhas):
        data[f"ingredientes-{i}-ingrediente"] = str(linha["ingrediente"])
        data[f"ingredientes-{i}-quantidade"] = str(linha["quantidade"])
        data[f"ingredientes-{i}-unidade"] = linha.get("unidade", "g")
        if linha.get("principal", True):
            data[f"ingredientes-{i}-principal"] = "on"
        if "id" in linha:
            data[f"ingredientes-{i}-id"] = str(linha["id"])
        if linha.get("delete"):
            data[f"ingredientes-{i}-DELETE"] = "on"
    return data


# --------------------------------------------------------------------------- #
# Acesso / RBAC
# --------------------------------------------------------------------------- #
def test_lista_renderiza_para_gerente(client_gerente):
    resp = client_gerente.get(reverse("fichas:ficha_list"))
    assert resp.status_code == 200


@pytest.mark.parametrize("perfil", ["garcom", "almoxarife"])
def test_perfil_sem_acesso_recebe_403(client, make_perfil, perfil):
    client.force_login(make_perfil(perfil))
    resp = client.get(reverse("fichas:ficha_list"))
    assert resp.status_code == 403


def test_nao_autenticado_redireciona(client):
    resp = client.get(reverse("fichas:ficha_list"))
    assert resp.status_code == 302
    assert "login" in resp.url


# --------------------------------------------------------------------------- #
# Criação + cálculo de custo
# --------------------------------------------------------------------------- #
def test_criar_ficha_calcula_custo_e_snapshot(client_gerente, restaurante, ing_carne):
    resp = client_gerente.post(
        reverse("fichas:ficha_nova"),
        _ficha_post(
            "Hambúrguer",
            rendimento=2,
            linhas=[{"ingrediente": ing_carne.pk, "quantidade": "200", "unidade": "g"}],
        ),
    )
    assert resp.status_code == 302

    ficha = FichaTecnica.objects.get(nome="Hambúrguer")
    assert ficha.restaurante == restaurante
    # custo_total = 200 * 0.05 = 10; custo_porcao = 10 / 2 = 5
    assert ficha.custo_total == Decimal("10.0000")
    assert ficha.custo_porcao == Decimal("5.0000")
    linha = ficha.ingredientes.get()
    assert linha.custo_snapshot == Decimal("0.0500")


def test_ficha_exige_ao_menos_um_ingrediente(client_gerente):
    data = _ficha_post("Vazia", rendimento=1, linhas=[])
    data["ingredientes-TOTAL_FORMS"] = "1"  # 1 form em branco
    resp = client_gerente.post(reverse("fichas:ficha_nova"), data)
    assert resp.status_code == 200  # re-renderiza com erro
    assert not FichaTecnica.objects.filter(nome="Vazia").exists()


# --------------------------------------------------------------------------- #
# Edição + cascata para o Prato (§3B nível 2)
# --------------------------------------------------------------------------- #
def test_editar_ficha_recalcula_e_propaga_para_prato(client_gerente, prato, ingrediente):
    # prato.ficha tem 1 linha (Carne Moída, qtd 200) com custo 0 -> custo_porcao 0
    ingrediente.custo_unitario = Decimal("0.05")
    ingrediente.save(update_fields=["custo_unitario"])
    ficha = prato.ficha
    linha = ficha.ingredientes.get()

    resp = client_gerente.post(
        reverse("fichas:ficha_editar", args=[ficha.pk]),
        _ficha_post(
            ficha.nome,
            rendimento=1,
            linhas=[
                {
                    "id": linha.pk,
                    "ingrediente": ingrediente.pk,
                    "quantidade": "200",
                    "unidade": "g",
                }
            ],
            initial=1,
        ),
    )
    assert resp.status_code == 302

    ficha.refresh_from_db()
    assert ficha.custo_porcao == Decimal("10.0000")  # 200 * 0.05 / 1
    prato.refresh_from_db()
    assert prato.custo_atual == Decimal("10.0000")
    # margem = (30 - 10) / 30 * 100 = 66.67
    assert prato.margem_lucro == Decimal("66.67")


def test_remover_linha_via_delete(client_gerente, restaurante, ing_carne):
    ing2 = Ingrediente.objects.create(
        restaurante=restaurante, nome="Sal", unidade_medida="g",
        custo_unitario=Decimal("0.01"),
    )
    ficha = FichaTecnica.objects.create(restaurante=restaurante, nome="Mix", rendimento=1)
    l1 = FichaIngrediente.objects.create(
        ficha=ficha, ingrediente=ing_carne, quantidade=Decimal("100"), unidade="g"
    )
    l2 = FichaIngrediente.objects.create(
        ficha=ficha, ingrediente=ing2, quantidade=Decimal("50"), unidade="g"
    )

    resp = client_gerente.post(
        reverse("fichas:ficha_editar", args=[ficha.pk]),
        _ficha_post(
            "Mix",
            rendimento=1,
            linhas=[
                {"id": l1.pk, "ingrediente": ing_carne.pk, "quantidade": "100", "unidade": "g"},
                {"id": l2.pk, "ingrediente": ing2.pk, "quantidade": "50", "unidade": "g", "delete": True},
            ],
            initial=2,
        ),
    )
    assert resp.status_code == 302
    assert ficha.ingredientes.count() == 1
    ficha.refresh_from_db()
    assert ficha.custo_total == Decimal("5.0000")  # 100 * 0.05


# --------------------------------------------------------------------------- #
# Exclusão + multi-tenant
# --------------------------------------------------------------------------- #
def test_excluir_ficha(client_gerente, restaurante):
    ficha = FichaTecnica.objects.create(restaurante=restaurante, nome="Temp", rendimento=1)
    resp = client_gerente.post(reverse("fichas:ficha_excluir", args=[ficha.pk]))
    assert resp.status_code == 302
    assert not FichaTecnica.objects.filter(pk=ficha.pk).exists()


def test_excluir_ficha_com_prato_e_bloqueada(client_gerente, prato):
    resp = client_gerente.post(reverse("fichas:ficha_excluir", args=[prato.ficha_id]))
    assert resp.status_code == 200  # PROTECT -> re-renderiza com erro
    assert FichaTecnica.objects.filter(pk=prato.ficha_id).exists()


def test_ficha_de_outro_tenant(client_gerente, outro_restaurante):
    alheia = FichaTecnica.objects.create(
        restaurante=outro_restaurante, nome="FichaAlheia", rendimento=1
    )
    # não aparece na lista
    resp = client_gerente.get(reverse("fichas:ficha_list"))
    assert b"FichaAlheia" not in resp.content
    # não pode editar (404 pelo escopo de tenant)
    resp = client_gerente.get(reverse("fichas:ficha_editar", args=[alheia.pk]))
    assert resp.status_code == 404
