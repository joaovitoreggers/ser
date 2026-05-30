from __future__ import annotations

from django.contrib.auth import login
from django.contrib.auth.models import User
from django.contrib.auth.views import LoginView
from django.http import HttpRequest, JsonResponse
from django.urls import reverse
from django.views.decorators.http import require_POST
from django.views.generic import TemplateView

from .rbac import PERFIL_REDIRECT


def redirect_para_perfil(user) -> str:
    """URL pós-login conforme o perfil do usuário (§5)."""
    perfil = getattr(user, "perfil", None)
    nome = perfil.perfil if perfil else None
    return reverse(PERFIL_REDIRECT.get(nome, "home"))


class PerfilLoginView(LoginView):
    template_name = "registration/login.html"
    redirect_authenticated_user = True

    def get_success_url(self) -> str:
        url = self.get_redirect_url()  # respeita ?next=
        return url or redirect_para_perfil(self.request.user)


class PinPadView(TemplateView):
    """Tela de acesso rápido por teclado numérico para tablets (§5).

    Renderiza o teclado (Alpine.js) que envia usuário + PIN ao endpoint
    ``pin_login`` via fetch; a validação do ``pin_hash`` continua no servidor.
    """

    template_name = "registration/pin_login.html"


@require_POST
def pin_login(request: HttpRequest) -> JsonResponse:
    """Login por teclado numérico para telas operacionais de tablet (§5).

    Espera POST {username, pin}. Valida contra pin_hash e autentica a sessão.
    """
    username = request.POST.get("username", "").strip()
    pin = request.POST.get("pin", "").strip()

    user = User.objects.filter(username=username, is_active=True).first()
    perfil = getattr(user, "perfil", None) if user else None

    if perfil is None or not perfil.check_pin(pin):
        return JsonResponse({"ok": False, "erro": "Credenciais inválidas."}, status=401)

    login(request, user)
    return JsonResponse({"ok": True, "redirect": redirect_para_perfil(user)})
