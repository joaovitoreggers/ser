from __future__ import annotations

import pytest
from django.contrib.auth.models import Group, User
from django.urls import reverse

from apps.usuarios.models import PerfilUsuario

pytestmark = pytest.mark.django_db

SENHA = "senha-forte-123"


def test_rbac_gerente_gerencia_perfilusuario():
    """O gerente recebe add/change/view de perfilusuario (gestão da equipe),
    mas não delete (exclusão física não é exposta)."""
    cods = set(
        Group.objects.get(name="gerente").permissions.values_list("codename", flat=True)
    )
    assert {"add_perfilusuario", "change_perfilusuario", "view_perfilusuario"} <= cods
    assert "delete_perfilusuario" not in cods


def _login(client, perfil):
    assert client.login(username=f"{perfil}_user", password=SENHA)


# --------------------------------------------------------------------------- #
# Card na home + controle de acesso
# --------------------------------------------------------------------------- #
def test_card_usuarios_visivel_para_admin(client, make_perfil):
    make_perfil("admin")
    _login(client, "admin")
    body = client.get(reverse("home")).content.decode()
    assert reverse("usuarios:usuario_list") in body
    assert "Usuários" in body


def test_card_usuarios_oculto_para_garcom(client, make_perfil):
    make_perfil("garcom")
    _login(client, "garcom")
    body = client.get(reverse("home")).content.decode()
    assert reverse("usuarios:usuario_list") not in body


@pytest.mark.parametrize("perfil", ["admin", "gerente"])
def test_gestao_acessivel_para_gestores(client, make_perfil, perfil):
    make_perfil(perfil)
    _login(client, perfil)
    resp = client.get(reverse("usuarios:usuario_list"))
    assert resp.status_code == 200


@pytest.mark.parametrize("perfil", ["garcom", "cozinheiro", "caixa", "almoxarife"])
def test_gestao_bloqueada_para_operacionais(client, make_perfil, perfil):
    make_perfil(perfil)
    _login(client, perfil)
    resp = client.get(reverse("usuarios:usuario_list"))
    assert resp.status_code == 403


def test_gestao_exige_login(client):
    resp = client.get(reverse("usuarios:usuario_list"))
    assert resp.status_code == 302
    assert reverse("usuarios:login") in resp.url


# --------------------------------------------------------------------------- #
# Criação
# --------------------------------------------------------------------------- #
def test_admin_cria_usuario_com_perfil_grupo_e_pin(client, make_perfil, restaurante):
    make_perfil("admin")
    _login(client, "admin")
    resp = client.post(
        reverse("usuarios:usuario_novo"),
        {
            "username": "novo_garcom",
            "nome": "Maria Silva",
            "email": "maria@ex.com",
            "perfil": "garcom",
            "senha": "supersenha123",
            "pin": "4321",
            "ativo": "on",
        },
    )
    assert resp.headers.get("HX-Trigger") == "usuarios:changed"

    u = User.objects.get(username="novo_garcom")
    assert u.check_password("supersenha123")
    assert u.is_active
    assert u.groups.filter(name="garcom").exists()
    p = u.perfil
    assert p.restaurante_id == restaurante.id
    assert p.perfil == "garcom"
    assert p.check_pin("4321")


def test_username_duplicado_rejeitado(client, make_perfil):
    make_perfil("admin")  # cria admin_user
    _login(client, "admin")
    resp = client.post(
        reverse("usuarios:usuario_novo"),
        {"username": "admin_user", "perfil": "caixa", "senha": "supersenha123", "ativo": "on"},
    )
    assert "HX-Trigger" not in resp.headers  # formulário inválido, não criou


def test_pin_invalido_rejeitado(client, make_perfil):
    make_perfil("admin")
    _login(client, "admin")
    resp = client.post(
        reverse("usuarios:usuario_novo"),
        {"username": "u1", "perfil": "caixa", "senha": "supersenha123", "pin": "12", "ativo": "on"},
    )
    assert "HX-Trigger" not in resp.headers
    assert not User.objects.filter(username="u1").exists()


def test_senha_curta_rejeitada(client, make_perfil):
    make_perfil("admin")
    _login(client, "admin")
    resp = client.post(
        reverse("usuarios:usuario_novo"),
        {"username": "u2", "perfil": "caixa", "senha": "123", "ativo": "on"},
    )
    assert "HX-Trigger" not in resp.headers
    assert not User.objects.filter(username="u2").exists()


# --------------------------------------------------------------------------- #
# Edição
# --------------------------------------------------------------------------- #
def test_edicao_muda_perfil_e_grupo_mantendo_senha(client, make_perfil):
    make_perfil("admin")
    _login(client, "admin")
    alvo = make_perfil("garcom")  # garcom_user, senha padrão

    resp = client.post(
        reverse("usuarios:usuario_editar", args=[alvo.perfil.pk]),
        {
            "nome": "Outro Nome",
            "email": "novo@ex.com",
            "perfil": "caixa",
            "senha": "",  # em branco mantém
            "pin": "",
            "ativo": "on",
        },
    )
    assert resp.headers.get("HX-Trigger") == "usuarios:changed"

    alvo.refresh_from_db()
    assert alvo.check_password(SENHA)  # senha preservada
    assert alvo.first_name == "Outro Nome"
    assert alvo.perfil.perfil == "caixa"
    assert alvo.groups.filter(name="caixa").exists()
    assert not alvo.groups.filter(name="garcom").exists()


def test_edicao_redefine_senha_quando_informada(client, make_perfil):
    make_perfil("admin")
    _login(client, "admin")
    alvo = make_perfil("caixa")

    resp = client.post(
        reverse("usuarios:usuario_editar", args=[alvo.perfil.pk]),
        {"perfil": "caixa", "senha": "trocada-99999", "pin": "", "ativo": "on"},
    )
    assert resp.headers.get("HX-Trigger") == "usuarios:changed"
    alvo.refresh_from_db()
    assert alvo.check_password("trocada-99999")


# --------------------------------------------------------------------------- #
# Ativar / desativar
# --------------------------------------------------------------------------- #
def test_toggle_desativa_e_reativa(client, make_perfil):
    make_perfil("admin")
    _login(client, "admin")
    alvo = make_perfil("garcom")

    resp = client.post(reverse("usuarios:usuario_status", args=[alvo.perfil.pk]))
    assert resp.headers.get("HX-Trigger") == "usuarios:changed"
    alvo.refresh_from_db()
    assert alvo.is_active is False

    client.post(reverse("usuarios:usuario_status", args=[alvo.perfil.pk]))
    alvo.refresh_from_db()
    assert alvo.is_active is True


def test_nao_pode_desativar_a_si_mesmo(client, make_perfil):
    admin = make_perfil("admin")
    _login(client, "admin")
    resp = client.post(reverse("usuarios:usuario_status", args=[admin.perfil.pk]))
    assert resp.status_code == 403
    admin.refresh_from_db()
    assert admin.is_active is True


# --------------------------------------------------------------------------- #
# Guardas de privilégio do gerente (não mexe em admin)
# --------------------------------------------------------------------------- #
def test_gerente_nao_atribui_perfil_admin(client, make_perfil):
    make_perfil("gerente")
    _login(client, "gerente")
    resp = client.post(
        reverse("usuarios:usuario_novo"),
        {"username": "fake_admin", "perfil": "admin", "senha": "supersenha123", "ativo": "on"},
    )
    assert "HX-Trigger" not in resp.headers
    assert not User.objects.filter(username="fake_admin").exists()


def test_gerente_nao_edita_admin(client, make_perfil):
    make_perfil("gerente")
    _login(client, "gerente")
    admin = make_perfil("admin")
    resp = client.get(reverse("usuarios:usuario_editar", args=[admin.perfil.pk]))
    assert resp.status_code == 404


def test_gerente_nao_lista_admin(client, make_perfil):
    make_perfil("gerente")
    _login(client, "gerente")
    make_perfil("admin")
    make_perfil("garcom")
    body = client.get(reverse("usuarios:usuario_list")).content.decode()
    assert "garcom_user" in body
    assert "gerente_user" in body
    assert "admin_user" not in body


# --------------------------------------------------------------------------- #
# Isolamento multi-tenant
# --------------------------------------------------------------------------- #
def test_lista_isola_por_tenant(client, make_perfil, outro_restaurante):
    make_perfil("admin")
    _login(client, "admin")
    alheio = User.objects.create_user(username="alheio", password="x")
    PerfilUsuario.objects.create(
        user=alheio, restaurante=outro_restaurante, perfil="garcom"
    )
    body = client.get(reverse("usuarios:usuario_list")).content.decode()
    assert "alheio" not in body
