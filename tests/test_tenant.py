from __future__ import annotations

from decimal import Decimal

import pytest

from apps.estoque.models import Ingrediente, UnidadeMedida

pytestmark = pytest.mark.django_db


def test_for_tenant_isola_restaurantes(restaurante, outro_restaurante):
    Ingrediente.objects.create(
        restaurante=restaurante, nome="Sal", unidade_medida=UnidadeMedida.GRAMA
    )
    Ingrediente.objects.create(
        restaurante=outro_restaurante, nome="Açúcar", unidade_medida=UnidadeMedida.GRAMA
    )

    meus = Ingrediente.objects.for_tenant(restaurante)
    assert meus.count() == 1
    assert meus.first().nome == "Sal"

    outros = Ingrediente.objects.for_tenant(outro_restaurante)
    assert outros.count() == 1
    assert outros.first().nome == "Açúcar"


def test_pin_hash_argon2(restaurante, django_user_model):
    from apps.usuarios.models import PerfilUsuario

    u = django_user_model.objects.create_user(username="gerente1", password="x")
    perfil = PerfilUsuario(
        user=u, restaurante=restaurante, perfil=PerfilUsuario.Perfil.GERENTE
    )
    perfil.set_pin("1234")
    perfil.save()

    assert perfil.pin_hash.startswith("argon2")
    assert perfil.check_pin("1234")
    assert not perfil.check_pin("0000")
