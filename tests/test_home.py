from __future__ import annotations

import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


def test_home_exige_login(client):
    resp = client.get("/")
    assert resp.status_code == 302
    assert reverse("usuarios:login") in resp.url


def test_home_url_resolve_para_raiz():
    assert reverse("home") == "/"


@pytest.mark.parametrize(
    "perfil", ["admin", "gerente", "garcom", "cozinheiro", "caixa", "almoxarife"]
)
def test_home_acessivel_a_todos_os_perfis(client, make_perfil, perfil):
    make_perfil(perfil, senha="senha-forte-123")
    client.login(username=f"{perfil}_user", password="senha-forte-123")
    resp = client.get("/")
    assert resp.status_code == 200
    assert "Acessar recursos" in resp.content.decode()


def test_home_gestor_ve_faturamento(client, make_perfil):
    make_perfil("gerente", senha="senha-forte-123")
    client.login(username="gerente_user", password="senha-forte-123")
    body = client.get("/").content.decode()
    assert "Faturamento" in body
    assert "Financeiro" in body  # card de financeiro
    assert "Receitas" in body  # card de receitas


def test_sidebar_nao_vaza_comentarios_de_template(client, make_perfil):
    """Regressão: comentário {# #} multilinha era renderizado como texto."""
    make_perfil("gerente", senha="senha-forte-123")
    client.login(username="gerente_user", password="senha-forte-123")
    body = client.get(reverse("estoque:home")).content.decode()
    # Itens da sidebar presentes...
    assert "Ingredientes" in body
    assert "Fornecedores" in body
    # ...mas nenhum comentário de template vazado.
    assert "{#" not in body
    assert "navegação da sidebar" not in body


def test_home_garcom_nao_ve_faturamento_nem_card_financeiro(client, make_perfil):
    make_perfil("garcom", senha="senha-forte-123")
    client.login(username="garcom_user", password="senha-forte-123")
    body = client.get("/").content.decode()
    assert "Faturamento" not in body  # indicador financeiro oculto
    assert "Pedidos" in body  # card de pedidos visível
    # garçom não enxerga os cards de financeiro/fichas
    assert "Caixa, turnos e pagamentos." not in body
    assert "Receitas e cardápio." not in body
