from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model

from apps.cardapio.models import CategoriaPrato, Prato
from apps.core.models import Restaurante
from apps.estoque.models import Ingrediente, UnidadeMedida
from apps.fichas.models import FichaIngrediente, FichaTecnica

User = get_user_model()


@pytest.fixture
def restaurante(db):
    return Restaurante.objects.create(
        nome="Cantina Teste", cnpj="11.111.111/0001-11", margem_padrao=Decimal("60.00")
    )


@pytest.fixture
def outro_restaurante(db):
    return Restaurante.objects.create(
        nome="Bar Rival", cnpj="22.222.222/0001-22", margem_padrao=Decimal("50.00")
    )


@pytest.fixture
def user(db):
    return User.objects.create_user(username="garcom1", password="x")


@pytest.fixture
def make_perfil(db, restaurante):
    """Cria User + PerfilUsuario no grupo correspondente, com PIN opcional."""
    from django.contrib.auth.models import Group

    from apps.usuarios.models import PerfilUsuario

    def _make(perfil: str, *, senha: str = "senha-forte-123", pin: str | None = None):
        u = User.objects.create_user(username=f"{perfil}_user", password=senha)
        grupo, _ = Group.objects.get_or_create(name=perfil)
        u.groups.add(grupo)
        p = PerfilUsuario(user=u, restaurante=restaurante, perfil=perfil)
        if pin:
            p.set_pin(pin)
        p.save()
        return u

    return _make


@pytest.fixture
def ingrediente(restaurante):
    return Ingrediente.objects.create(
        restaurante=restaurante,
        nome="Carne Moída",
        unidade_medida=UnidadeMedida.GRAMA,
        estoque_atual=Decimal("0"),
        estoque_minimo=Decimal("500"),
        custo_unitario=Decimal("0"),
    )


@pytest.fixture
def ficha(restaurante, ingrediente):
    f = FichaTecnica.objects.create(
        restaurante=restaurante, nome="Hambúrguer", rendimento=1
    )
    FichaIngrediente.objects.create(
        ficha=f,
        ingrediente=ingrediente,
        quantidade=Decimal("200"),
        unidade="g",
        principal=True,
    )
    return f


@pytest.fixture
def prato(restaurante, ficha):
    categoria = CategoriaPrato.objects.create(restaurante=restaurante, nome="Lanches")
    return Prato.objects.create(
        restaurante=restaurante,
        ficha=ficha,
        categoria=categoria,
        nome="Hambúrguer Clássico",
        preco_venda=Decimal("30.00"),
    )
