from __future__ import annotations

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse


class TenantMixin(LoginRequiredMixin):
    """Garante autenticação e fixa self.restaurante a partir do PerfilUsuario.

    IMPORTANTE: self.restaurante é definido ANTES de super().dispatch(), porque
    View.dispatch() chama get()/post() → get_queryset(), que precisa do tenant.
    """

    restaurante = None

    def dispatch(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        if not request.user.is_authenticated:
            return self.handle_no_permission()

        perfil = getattr(request.user, "perfil", None)
        if perfil is None:
            raise PermissionDenied("Usuário sem perfil/restaurante associado.")
        self.restaurante = perfil.restaurante

        return super().dispatch(request, *args, **kwargs)


class TenantQuerysetMixin(TenantMixin):
    """Escopa automaticamente o queryset ao restaurante do usuário."""

    def get_queryset(self):
        return super().get_queryset().for_tenant(self.restaurante)


class PerfilRequiredMixin(TenantMixin):
    """Restringe a view a um conjunto de perfis (grupos Django, §5)."""

    perfis_permitidos: tuple[str, ...] = ()

    def dispatch(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        if not request.user.is_authenticated:
            return self.handle_no_permission()

        perfil = getattr(request.user, "perfil", None)
        if perfil is None:
            raise PermissionDenied("Usuário sem perfil/restaurante associado.")

        if self.perfis_permitidos and perfil.perfil not in self.perfis_permitidos:
            raise PermissionDenied("Perfil sem acesso a este recurso.")

        return super().dispatch(request, *args, **kwargs)
