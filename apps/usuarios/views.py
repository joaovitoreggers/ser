from __future__ import annotations

from django.contrib.auth import login
from django.contrib.auth.models import User
from django.contrib.auth.views import LoginView
from django.http import HttpRequest, HttpResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.http import require_POST
from django.views.generic import TemplateView, View

from apps.core.mixins import PerfilRequiredMixin

from .forms import UsuarioForm
from .models import PerfilUsuario
from .rbac import PERFIL_REDIRECT

CHANGED_EVENT = "usuarios:changed"


def _trigger_response() -> HttpResponse:
    """Fecha o modal (#modal recebe innerHTML vazio) e dispara o evento HTMX que
    recarrega a tabela da listagem."""
    resp = HttpResponse("")
    resp["HX-Trigger"] = CHANGED_EVENT
    return resp


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


# --------------------------------------------------------------------------- #
# Gestão de usuários (§5) — admin e gerente
# --------------------------------------------------------------------------- #
class GestaoUsuariosAccessMixin(PerfilRequiredMixin):
    """Acesso ao módulo de gestão de usuários. PerfilRequiredMixin já fixa
    self.restaurante antes do dispatch (não listar TenantMixin separadamente)."""

    perfis_permitidos = ("admin", "gerente")

    def usuarios_do_tenant(self):
        qs = (
            PerfilUsuario.objects.for_tenant(self.restaurante)
            .select_related("user")
            .order_by("user__username")
        )
        # Gerente não enxerga (nem gerencia) administradores.
        if self.request.user.perfil.perfil == "gerente":
            qs = qs.exclude(perfil="admin")
        return qs

    def get_alvo(self, pk) -> PerfilUsuario:
        return get_object_or_404(self.usuarios_do_tenant(), pk=pk)


class UsuarioListView(GestaoUsuariosAccessMixin, View):
    template_name = "usuarios/usuario_list.html"

    def get(self, request):
        return render(
            request, self.template_name, {"object_list": self.usuarios_do_tenant()}
        )


class UsuarioTabelaView(UsuarioListView):
    template_name = "usuarios/_usuario_tabela.html"


class UsuarioCreateView(GestaoUsuariosAccessMixin, View):
    template_name = "estoque/_form_modal.html"
    titulo = "Novo usuário"

    def _ctx(self, form):
        return {"form": form, "titulo": self.titulo, "action_url": self.request.path}

    def get(self, request):
        form = UsuarioForm(
            restaurante=self.restaurante, ator_perfil=request.user.perfil.perfil
        )
        return render(request, self.template_name, self._ctx(form))

    def post(self, request):
        form = UsuarioForm(
            request.POST,
            restaurante=self.restaurante,
            ator_perfil=request.user.perfil.perfil,
        )
        if form.is_valid():
            form.save()
            return _trigger_response()
        return render(request, self.template_name, self._ctx(form))


class UsuarioUpdateView(GestaoUsuariosAccessMixin, View):
    template_name = "estoque/_form_modal.html"
    titulo = "Editar usuário"

    def _ctx(self, form):
        return {"form": form, "titulo": self.titulo, "action_url": self.request.path}

    def get(self, request, pk):
        alvo = self.get_alvo(pk)
        form = UsuarioForm(
            restaurante=self.restaurante,
            ator_perfil=request.user.perfil.perfil,
            instance=alvo,
        )
        return render(request, self.template_name, self._ctx(form))

    def post(self, request, pk):
        alvo = self.get_alvo(pk)
        form = UsuarioForm(
            request.POST,
            restaurante=self.restaurante,
            ator_perfil=request.user.perfil.perfil,
            instance=alvo,
        )
        if form.is_valid():
            form.save()
            return _trigger_response()
        return render(request, self.template_name, self._ctx(form))


class UsuarioToggleAtivoView(GestaoUsuariosAccessMixin, View):
    """Ativa/desativa o usuário (preferível a excluir: preserva o histórico de
    pedidos, turnos e movimentações)."""

    def post(self, request, pk):
        alvo = self.get_alvo(pk)
        if alvo.user_id == request.user.id:
            return HttpResponseForbidden("Você não pode desativar a própria conta.")
        alvo.user.is_active = not alvo.user.is_active
        alvo.user.save(update_fields=["is_active"])
        return _trigger_response()
