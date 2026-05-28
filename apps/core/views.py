from __future__ import annotations

from django.http import HttpResponse
from django.views import View

from .mixins import PerfilRequiredMixin


class StubPageView(PerfilRequiredMixin, View):
    """Landing page mínima por perfil (§5). Será substituída pelas telas reais
    nas próximas fases; por ora confirma RBAC + escopo de tenant funcionando."""

    page_name = "página"

    def get(self, request, *args, **kwargs) -> HttpResponse:
        return HttpResponse(
            f"{self.page_name} — {self.restaurante.nome} "
            f"({request.user.perfil.get_perfil_display()})"
        )
