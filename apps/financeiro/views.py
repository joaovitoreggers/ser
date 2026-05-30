from __future__ import annotations

from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.generic import View

from apps.core.mixins import PerfilRequiredMixin, TenantMixin
from apps.pedidos.services import registrar_log, validar_pin_aprovador

from apps.pedidos.models import ItemPedido, Pedido

from .forms import AbrirTurnoForm, FecharTurnoForm, MovimentacaoForm
from .models import MovimentacaoCaixa, TurnoCaixa
from .services import get_turno_aberto, pagamentos_do_turno, resumo_turno

CHANGED_EVENT = "financeiro:changed"


def _trigger_response() -> HttpResponse:
    """Fecha o modal HTMX e dispara o recarregamento do painel/tabela."""
    resp = HttpResponse("")
    resp["HX-Trigger"] = CHANGED_EVENT
    return resp


class FinanceiroAccessMixin(PerfilRequiredMixin):
    """Caixa/financeiro: caixa, gerente e admin (§5)."""

    perfis_permitidos = ("caixa", "gerente", "admin")


# --------------------------------------------------------------------------- #
# Painel do turno de caixa
# --------------------------------------------------------------------------- #
class CaixaTurnoView(FinanceiroAccessMixin, TenantMixin, View):
    template_name = "financeiro/caixa_turno.html"
    partial_name = "financeiro/_painel_turno.html"

    def _context(self):
        turno = get_turno_aberto(self.restaurante)
        ctx = {"turno": turno}
        if turno is not None:
            ctx["resumo"] = resumo_turno(turno)
            ctx["movimentacoes"] = turno.movimentacoes.select_related(
                "usuario", "autorizado_por"
            ).order_by("-criado_em")
        return ctx

    def get(self, request):
        template = self.partial_name if request.headers.get("HX-Request") else self.template_name
        return render(request, template, self._context())


# --------------------------------------------------------------------------- #
# Abertura / fechamento de turno
# --------------------------------------------------------------------------- #
class TurnoAbrirView(FinanceiroAccessMixin, TenantMixin, View):
    template_name = "estoque/_form_modal.html"

    def _render(self, request, form):
        return render(
            request,
            self.template_name,
            {"form": form, "titulo": "Abrir caixa", "action_url": request.path},
        )

    def get(self, request):
        if get_turno_aberto(self.restaurante):
            return redirect("financeiro:home")
        return self._render(request, AbrirTurnoForm())

    def post(self, request):
        if get_turno_aberto(self.restaurante):
            return HttpResponse("Já existe um turno de caixa aberto.", status=409)
        form = AbrirTurnoForm(request.POST)
        if not form.is_valid():
            return self._render(request, form)
        turno = form.save(commit=False)
        turno.restaurante = self.restaurante
        turno.usuario = request.user
        turno.status = TurnoCaixa.Status.ABERTO
        turno.save()
        registrar_log(
            restaurante=self.restaurante,
            usuario=request.user,
            acao="abrir_turno",
            entidade="TurnoCaixa",
            entidade_id=turno.id,
            dados_depois={"valor_abertura": str(turno.valor_abertura)},
        )
        return _trigger_response()


class TurnoFecharView(FinanceiroAccessMixin, TenantMixin, View):
    template_name = "financeiro/turno_fechar.html"

    def _get_turno(self):
        return get_object_or_404(
            TurnoCaixa.objects.for_tenant(self.restaurante),
            status=TurnoCaixa.Status.ABERTO,
        )

    def _render(self, request, turno, form):
        return render(
            request,
            self.template_name,
            {
                "turno": turno,
                "form": form,
                "resumo": resumo_turno(turno),
                "action_url": request.path,
            },
        )

    def get(self, request):
        turno = self._get_turno()
        return self._render(request, turno, FecharTurnoForm(instance=turno))

    def post(self, request):
        turno = self._get_turno()
        form = FecharTurnoForm(request.POST, instance=turno)
        if not form.is_valid():
            return self._render(request, turno, form)
        resumo = resumo_turno(turno)
        turno = form.save(commit=False)
        turno.status = TurnoCaixa.Status.FECHADO
        turno.fechado_em = timezone.now()
        turno.save(update_fields=["valor_fechamento", "status", "fechado_em"])
        diferenca = turno.valor_fechamento - resumo["saldo_esperado"]
        registrar_log(
            restaurante=self.restaurante,
            usuario=request.user,
            acao="fechar_turno",
            entidade="TurnoCaixa",
            entidade_id=turno.id,
            dados_depois={
                "saldo_esperado": str(resumo["saldo_esperado"]),
                "valor_fechamento": str(turno.valor_fechamento),
                "diferenca": str(diferenca),
            },
        )
        return _trigger_response()


# --------------------------------------------------------------------------- #
# Sangria / suprimento
# --------------------------------------------------------------------------- #
class MovimentacaoCreateView(FinanceiroAccessMixin, TenantMixin, View):
    template_name = "estoque/_form_modal.html"

    def _render(self, request, form):
        return render(
            request,
            self.template_name,
            {"form": form, "titulo": "Sangria / suprimento", "action_url": request.path},
        )

    def get(self, request):
        return self._render(request, MovimentacaoForm())

    def post(self, request):
        turno = get_turno_aberto(self.restaurante)
        if turno is None:
            return HttpResponse("Nenhum turno de caixa aberto.", status=409)
        form = MovimentacaoForm(request.POST)
        if not form.is_valid():
            return self._render(request, form)

        mov = form.save(commit=False)
        autorizador = None
        if mov.tipo == MovimentacaoCaixa.Tipo.SANGRIA:
            autorizador = validar_pin_aprovador(
                self.restaurante, form.cleaned_data.get("pin", "")
            )
            if autorizador is None:
                form.add_error(
                    "pin",
                    "Sangria exige PIN válido de um gerente/admin.",
                )
                return self._render(request, form)
            mov.autorizado_por = autorizador.user

        mov.turno = turno
        mov.usuario = request.user
        mov.save()
        registrar_log(
            restaurante=self.restaurante,
            usuario=request.user,
            acao="movimentacao_caixa",
            entidade="MovimentacaoCaixa",
            entidade_id=mov.id,
            dados_depois={
                "tipo": mov.tipo,
                "valor": str(mov.valor),
                "autorizado_por": str(autorizador) if autorizador else None,
            },
        )
        return _trigger_response()


# --------------------------------------------------------------------------- #
# Histórico de turnos
# --------------------------------------------------------------------------- #
class TurnoListView(FinanceiroAccessMixin, TenantMixin, View):
    template_name = "financeiro/turno_list.html"

    def get(self, request):
        turnos = list(
            TurnoCaixa.objects.for_tenant(self.restaurante)
            .select_related("usuario")
            .order_by("-aberto_em")
        )
        for turno in turnos:
            resumo = resumo_turno(turno)
            turno.saldo_esperado = resumo["saldo_esperado"]
            turno.total_recebido = resumo["total_pagamentos"]
            if turno.valor_fechamento is not None:
                turno.diferenca = turno.valor_fechamento - resumo["saldo_esperado"]
            else:
                turno.diferenca = None
        return render(request, self.template_name, {"turnos": turnos})


class TurnoDetailView(FinanceiroAccessMixin, TenantMixin, View):
    template_name = "financeiro/turno_detalhe.html"

    def get(self, request, pk):
        turno = get_object_or_404(
            TurnoCaixa.objects.for_tenant(self.restaurante).select_related("usuario"),
            pk=pk,
        )
        resumo = resumo_turno(turno)
        diferenca = (
            turno.valor_fechamento - resumo["saldo_esperado"]
            if turno.valor_fechamento is not None
            else None
        )
        pagamentos = (
            pagamentos_do_turno(turno)
            .select_related("pedido", "pedido__mesa", "usuario")
            .order_by("-criado_em")
        )
        movimentacoes = turno.movimentacoes.select_related(
            "usuario", "autorizado_por"
        ).order_by("-criado_em")
        return render(
            request,
            self.template_name,
            {
                "turno": turno,
                "resumo": resumo,
                "diferenca": diferenca,
                "pagamentos": pagamentos,
                "movimentacoes": movimentacoes,
            },
        )


# --------------------------------------------------------------------------- #
# Recibo / comprovante de pagamento
# --------------------------------------------------------------------------- #
class ReciboView(FinanceiroAccessMixin, TenantMixin, View):
    template_name = "financeiro/recibo.html"

    def get(self, request, pk):
        pedido = get_object_or_404(
            Pedido.objects.for_tenant(self.restaurante).select_related("mesa"),
            pk=pk,
        )
        itens = (
            pedido.itens.exclude(status=ItemPedido.Status.CANCELADO)
            .select_related("prato")
            .order_by("enviado_em", "id")
        )
        pagamentos = pedido.pagamentos.select_related("usuario").order_by("criado_em")
        return render(
            request,
            self.template_name,
            {"pedido": pedido, "itens": itens, "pagamentos": pagamentos},
        )
