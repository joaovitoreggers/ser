from __future__ import annotations

from django.shortcuts import render
from django.views.generic import View

from apps.core.mixins import PerfilRequiredMixin, TenantMixin

from .services import metricas_do_dia

# Perfis que enxergam indicadores financeiros (faturamento, ticket, caixa).
PERFIS_GESTAO = ("admin", "gerente")


class DashboardView(PerfilRequiredMixin, TenantMixin, View):
    """Painel gerencial (§5 admin/gerente): visão financeira + operacional do dia."""

    perfis_permitidos = PERFIS_GESTAO
    template_name = "relatorios/dashboard.html"

    def get(self, request):
        return render(request, self.template_name, metricas_do_dia(self.restaurante))


class HomeView(TenantMixin, View):
    """Tela principal (hub) em ``/``.

    Topo: dashboard geral das métricas do dia. Base: cards que levam a cada
    centralização de recursos (Estoque, Pedidos, Financeiro, Fichas). Os
    indicadores financeiros e os cards são filtrados por perfil (§5)."""

    template_name = "home.html"

    def get(self, request):
        perfil = request.user.perfil.perfil
        ctx = metricas_do_dia(self.restaurante)
        ctx.update(
            {
                "restaurante": self.restaurante,
                "perfil_nome": perfil,
                "perfil_label": request.user.perfil.get_perfil_display(),
                "is_gestor": perfil in PERFIS_GESTAO,
                "pode_estoque": perfil in ("admin", "gerente", "almoxarife"),
                "pode_pedidos": perfil
                in ("admin", "gerente", "garcom", "cozinheiro", "caixa"),
                "pode_financeiro": perfil in ("admin", "gerente", "caixa"),
                "pode_fichas": perfil in ("admin", "gerente"),
            }
        )
        return render(request, self.template_name, ctx)
