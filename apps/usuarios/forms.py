from __future__ import annotations

import re

from django import forms
from django.contrib.auth.models import Group, User
from django.db import transaction

from .models import PerfilUsuario

INPUT_CLASS = "w-full border border-gray-300 rounded px-3 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-500"
CHECKBOX_CLASS = "h-4 w-4 rounded border-gray-300 text-indigo-600"

PIN_RE = re.compile(r"^\d{4,8}$")


def perfis_disponiveis(ator_perfil: str) -> list[tuple[str, str]]:
    """Perfis que ``ator_perfil`` pode atribuir. Gerente não cria/edita admin
    (evita escalonamento de privilégio); admin atribui qualquer perfil."""
    choices = list(PerfilUsuario.Perfil.choices)
    if ator_perfil == "gerente":
        return [(v, label) for v, label in choices if v != "admin"]
    return choices


class UsuarioForm(forms.Form):
    """Cria/edita um usuário do restaurante: orquestra ``User`` (login, senha,
    status), ``PerfilUsuario`` (perfil + PIN) e o grupo Django de permissões.

    Em criação, ``username`` e ``senha`` são obrigatórios. Em edição, o
    ``username`` fica travado e ``senha``/``pin`` são opcionais (em branco
    mantêm o valor atual)."""

    username = forms.CharField(label="Usuário (login)", max_length=150)
    nome = forms.CharField(label="Nome completo", max_length=150, required=False)
    email = forms.EmailField(label="E-mail", required=False)
    perfil = forms.ChoiceField(label="Perfil de acesso")
    senha = forms.CharField(
        label="Senha", required=False, widget=forms.PasswordInput(render_value=False)
    )
    pin = forms.CharField(
        label="PIN (4 a 8 dígitos)",
        required=False,
        widget=forms.PasswordInput(render_value=False),
    )
    ativo = forms.BooleanField(label="Usuário ativo", required=False, initial=True)

    def __init__(self, *args, restaurante=None, ator_perfil=None, instance=None, **kwargs):
        self.restaurante = restaurante
        self.ator_perfil = ator_perfil
        self.instance = instance  # PerfilUsuario em edição, ou None na criação
        super().__init__(*args, **kwargs)

        self.fields["perfil"].choices = perfis_disponiveis(ator_perfil)

        if instance is not None:
            self.fields["username"].disabled = True
            self.fields["username"].initial = instance.user.username
            self.fields["nome"].initial = instance.user.first_name
            self.fields["email"].initial = instance.user.email
            self.fields["perfil"].initial = instance.perfil
            self.fields["ativo"].initial = instance.user.is_active
            self.fields["senha"].help_text = "Em branco mantém a senha atual."
            self.fields["pin"].help_text = "Em branco mantém o PIN atual."
        else:
            self.fields["senha"].required = True

        for field in self.fields.values():
            widget = field.widget
            base = CHECKBOX_CLASS if isinstance(widget, forms.CheckboxInput) else INPUT_CLASS
            existing = widget.attrs.get("class", "")
            widget.attrs["class"] = f"{existing} {base}".strip()

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        # username travado na edição: não revalida unicidade do próprio registro.
        if self.instance is None and User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("Já existe um usuário com esse login.")
        return username

    def clean_senha(self):
        senha = self.cleaned_data.get("senha", "")
        if senha and len(senha) < 8:
            raise forms.ValidationError("A senha deve ter ao menos 8 caracteres.")
        return senha

    def clean_pin(self):
        pin = (self.cleaned_data.get("pin") or "").strip()
        if pin and not PIN_RE.match(pin):
            raise forms.ValidationError("O PIN deve conter de 4 a 8 dígitos numéricos.")
        return pin

    def clean_perfil(self):
        perfil = self.cleaned_data["perfil"]
        validos = {v for v, _ in self.fields["perfil"].choices}
        if perfil not in validos:
            raise forms.ValidationError("Você não pode atribuir este perfil.")
        return perfil

    @transaction.atomic
    def save(self) -> PerfilUsuario:
        cd = self.cleaned_data

        if self.instance is None:
            user = User(username=cd["username"])
            user.set_password(cd["senha"])
        else:
            user = self.instance.user
            if cd.get("senha"):
                user.set_password(cd["senha"])
        user.first_name = cd.get("nome", "")
        user.email = cd.get("email", "")
        user.is_active = cd.get("ativo", False)
        user.save()

        perfil = self.instance or PerfilUsuario(user=user, restaurante=self.restaurante)
        perfil.perfil = cd["perfil"]
        if cd.get("pin"):
            perfil.set_pin(cd["pin"])
        perfil.save()

        # O grupo Django (= nome do perfil) carrega as permissões do RBAC (§5).
        grupo, _ = Group.objects.get_or_create(name=cd["perfil"])
        user.groups.set([grupo])
        return perfil
