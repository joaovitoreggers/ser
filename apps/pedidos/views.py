from __future__ import annotations

from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    UpdateView,
    View,
)

from apps.core.mixins import PerfilRequiredMixin, TenantQuerysetMixin

from .forms import CancelarItemForm, ItemPedidoForm, MesaForm, PagarPedidoForm
from .models import ItemPedido, Mesa, Pedido
from .services import registrar_log, validar_pin_aprovador

CHANGED_EVENT = "pedidos:changed"

ABERTOS = [Pedido.Status.ABERTO, Pedido.Status.EM_ATENDIMENTO, Pedido.Status.AGUARDANDO_PAGAMENTO]


def _trigger_response() -> HttpResponse:
    resp = HttpResponse("")
    resp["HX-Trigger"] = CHANGED_EVENT
    return resp


# --------------------------------------------------------------------------- #
# Access mixins (§5)
# --------------------------------------------------------------------------- #
class SalaoAccessMixin(PerfilRequiredMixin):
    """Salão (mesas/pedidos): garçom, gerente, admin."""

    perfis_permitidos = ("garcom", "gerente", "admin")


class GestaoMesaAccessMixin(PerfilRequiredMixin):
    """Cadastro de mesas: gerente, admin."""

    perfis_permitidos = ("gerente", "admin")


class KDSAccessMixin(PerfilRequiredMixin):
    """Cozinha (KDS): cozinheiro, gerente, admin."""

    perfis_permitidos = ("cozinheiro", "gerente", "admin")


class CaixaAccessMixin(PerfilRequiredMixin):
    """Caixa: caixa, gerente, admin."""

    perfis_permitidos = ("caixa", "gerente", "admin")


# --------------------------------------------------------------------------- #
# Mesas — board operacional + CRUD
# --------------------------------------------------------------------------- #
class MesaBoardView(SalaoAccessMixin, TenantQuerysetMixin, ListView):
    model = Mesa
    template_name = "pedidos/mesa_board.html"
    context_object_name = "mesas"
    ordering = ["numero"]

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        abertos = (
            Pedido.objects.for_tenant(self.restaurante)
            .filter(mesa__isnull=False, status__in=ABERTOS)
            .select_related("mesa")
        )
        por_mesa = {p.mesa_id: p for p in abertos}
        for mesa in ctx["mesas"]:
            mesa.pedido_aberto = por_mesa.get(mesa.id)
        return ctx


class MesaListView(GestaoMesaAccessMixin, TenantQuerysetMixin, ListView):
    model = Mesa
    template_name = "pedidos/mesa_list.html"
    context_object_name = "object_list"
    ordering = ["numero"]


class MesaTabelaView(MesaListView):
    template_name = "pedidos/_mesa_tabela.html"


class _MesaFormMixin:
    titulo = ""

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["restaurante"] = self.restaurante
        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["titulo"] = self.titulo
        ctx["action_url"] = self.request.path
        return ctx

    def form_valid(self, form):
        obj = form.save(commit=False)
        obj.restaurante = self.restaurante
        obj.save()
        return _trigger_response()


class MesaCreateView(GestaoMesaAccessMixin, _MesaFormMixin, CreateView):
    model = Mesa
    form_class = MesaForm
    template_name = "estoque/_form_modal.html"
    titulo = "Nova mesa"


class MesaUpdateView(
    GestaoMesaAccessMixin, TenantQuerysetMixin, _MesaFormMixin, UpdateView
):
    model = Mesa
    form_class = MesaForm
    template_name = "estoque/_form_modal.html"
    titulo = "Editar mesa"


class MesaDeleteView(GestaoMesaAccessMixin, TenantQuerysetMixin, DeleteView):
    model = Mesa
    template_name = "estoque/_confirm_delete.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["action_url"] = self.request.path
        return ctx

    def form_valid(self, form):
        from django.db.models import ProtectedError

        self.object = self.get_object()
        try:
            self.object.delete()
        except ProtectedError:
            ctx = self.get_context_data(object=self.object)
            ctx["erro"] = "Não é possível excluir: há pedidos vinculados a esta mesa."
            return self.render_to_response(ctx)
        return _trigger_response()


# --------------------------------------------------------------------------- #
# Pedido — abertura, detalhe (comanda), itens, envio
# --------------------------------------------------------------------------- #
class PedidoAbrirView(SalaoAccessMixin, TenantQuerysetMixin, View):
    """Abre (ou reabre) a comanda de uma mesa e redireciona para o detalhe."""

    def post(self, request, pk):
        mesa = get_object_or_404(
            Mesa.objects.for_tenant(self.restaurante), pk=pk
        )
        pedido = (
            Pedido.objects.for_tenant(self.restaurante)
            .filter(mesa=mesa, status__in=ABERTOS)
            .first()
        )
        if pedido is None:
            pedido = Pedido.objects.create(
                restaurante=self.restaurante,
                mesa=mesa,
                usuario=request.user,
                tipo=Pedido.Tipo.MESA,
            )
            mesa.status = Mesa.Status.OCUPADA
            mesa.save(update_fields=["status"])
        return redirect("pedidos:pedido_detalhe", pk=pedido.pk)


class PedidoBalcaoView(SalaoAccessMixin, View):
    def post(self, request):
        pedido = Pedido.objects.create(
            restaurante=self.restaurante,
            usuario=request.user,
            tipo=Pedido.Tipo.BALCAO,
        )
        return redirect("pedidos:pedido_detalhe", pk=pedido.pk)


class PedidoDetailView(SalaoAccessMixin, TenantQuerysetMixin, DetailView):
    model = Pedido
    template_name = "pedidos/pedido_detalhe.html"
    context_object_name = "pedido"

    def get_queryset(self):
        return super().get_queryset().select_related("mesa")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["itens"] = self.object.itens.select_related("prato").order_by("enviado_em", "id")
        ctx.setdefault("item_form", ItemPedidoForm(restaurante=self.restaurante))
        return ctx


class ItemAdicionarView(SalaoAccessMixin, TenantQuerysetMixin, View):
    def post(self, request, pk):
        pedido = get_object_or_404(
            Pedido.objects.for_tenant(self.restaurante), pk=pk
        )
        if pedido.pago:
            return HttpResponse("Pedido pago é somente leitura.", status=409)
        form = ItemPedidoForm(request.POST, restaurante=self.restaurante)
        if form.is_valid():
            item = form.save(commit=False)
            item.pedido = pedido
            item.save()  # congela snapshot de preço/custo (§4.2)
            pedido.recalcular_totais(save=True)
            return redirect("pedidos:pedido_detalhe", pk=pedido.pk)
        # Re-renderiza o detalhe com os erros do formulário.
        from django.shortcuts import render

        itens = pedido.itens.select_related("prato").order_by("enviado_em", "id")
        return render(
            request,
            "pedidos/pedido_detalhe.html",
            {"pedido": pedido, "itens": itens, "item_form": form},
        )


class PedidoEnviarView(SalaoAccessMixin, TenantQuerysetMixin, View):
    """Envia os itens 'aguardando' para a cozinha (status em_preparo)."""

    def post(self, request, pk):
        pedido = get_object_or_404(
            Pedido.objects.for_tenant(self.restaurante), pk=pk
        )
        if pedido.pago:
            return HttpResponse("Pedido pago é somente leitura.", status=409)
        agora = timezone.now()
        pendentes = pedido.itens.filter(status=ItemPedido.Status.AGUARDANDO)
        for item in pendentes:
            item.status = ItemPedido.Status.EM_PREPARO
            item.enviado_em = agora
            item.save(update_fields=["status", "enviado_em", "subtotal"])
        if pedido.status == Pedido.Status.ABERTO:
            pedido.status = Pedido.Status.EM_ATENDIMENTO
            pedido.save(update_fields=["status"])
        if pedido.mesa and pedido.mesa.status != Mesa.Status.EM_ATENDIMENTO:
            pedido.mesa.status = Mesa.Status.EM_ATENDIMENTO
            pedido.mesa.save(update_fields=["status"])
        return redirect("pedidos:pedido_detalhe", pk=pedido.pk)


class ItemCancelarView(SalaoAccessMixin, TenantQuerysetMixin, View):
    """Cancela um item (§4.4). 'aguardando' é livre; demais status exigem PIN
    de um aprovador (gerente/admin). Sempre exige motivo e gera LogAuditoria."""

    template_name = "pedidos/item_cancelar.html"

    def _get_item(self, pk):
        return get_object_or_404(
            ItemPedido.objects.select_related("pedido", "prato").filter(
                pedido__restaurante=self.restaurante
            ),
            pk=pk,
        )

    def _render(self, request, item, form):
        from django.shortcuts import render

        return render(
            request,
            self.template_name,
            {"item": item, "form": form, "pedido": item.pedido},
        )

    def get(self, request, pk):
        item = self._get_item(pk)
        return self._render(request, item, CancelarItemForm())

    def post(self, request, pk):
        item = self._get_item(pk)
        pedido = item.pedido
        if pedido.pago:
            return HttpResponse("Pedido pago é somente leitura.", status=409)
        form = CancelarItemForm(request.POST)
        if not form.is_valid():
            return self._render(request, item, form)

        exige_pin = item.status != ItemPedido.Status.AGUARDANDO
        aprovador = None
        if exige_pin:
            aprovador = validar_pin_aprovador(
                self.restaurante, form.cleaned_data.get("pin", "")
            )
            if aprovador is None:
                form.add_error(
                    "pin",
                    "PIN obrigatório e válido de um gerente/admin para cancelar "
                    "itens já enviados à cozinha.",
                )
                return self._render(request, item, form)

        status_antes = item.status
        item.status = ItemPedido.Status.CANCELADO
        item.motivo_cancelamento = form.cleaned_data["motivo"]
        item.save(update_fields=["status", "motivo_cancelamento", "subtotal"])
        pedido.recalcular_totais(save=True)

        registrar_log(
            restaurante=self.restaurante,
            usuario=request.user,
            acao="cancelar_item",
            entidade="ItemPedido",
            entidade_id=item.id,
            dados_antes={"status": status_antes},
            dados_depois={
                "status": item.status,
                "motivo": item.motivo_cancelamento,
                "aprovador": str(aprovador) if aprovador else None,
            },
        )
        return redirect("pedidos:pedido_detalhe", pk=pedido.pk)


# --------------------------------------------------------------------------- #
# KDS — cozinha
# --------------------------------------------------------------------------- #
class KDSView(KDSAccessMixin, View):
    template_name = "pedidos/kds.html"

    def get(self, request):
        from django.shortcuts import render

        itens = (
            ItemPedido.objects.filter(
                pedido__restaurante=self.restaurante,
                status__in=[ItemPedido.Status.EM_PREPARO, ItemPedido.Status.PRONTO],
            )
            .select_related("prato", "pedido", "pedido__mesa")
            .order_by("enviado_em", "id")
        )
        colunas = {
            ItemPedido.Status.EM_PREPARO: [],
            ItemPedido.Status.PRONTO: [],
        }
        for item in itens:
            colunas[item.status].append(item)
        return render(request, self.template_name, {"colunas": colunas})


class ItemAvancarView(KDSAccessMixin, View):
    """Avança o status do item: em_preparo → pronto → entregue (§5 cozinheiro
    só escreve em ``status``). 'pronto' dispara a baixa de estoque (§3C)."""

    PROXIMO = {
        ItemPedido.Status.EM_PREPARO: ItemPedido.Status.PRONTO,
        ItemPedido.Status.PRONTO: ItemPedido.Status.ENTREGUE,
    }

    def post(self, request, pk):
        item = get_object_or_404(
            ItemPedido.objects.filter(pedido__restaurante=self.restaurante),
            pk=pk,
        )
        proximo = self.PROXIMO.get(item.status)
        if proximo is not None:
            item.status = proximo
            item.save(update_fields=["status", "pronto_em", "subtotal"])
        return redirect("pedidos:kds")


# --------------------------------------------------------------------------- #
# Caixa — fechamento de pedidos
# --------------------------------------------------------------------------- #
class CaixaView(CaixaAccessMixin, TenantQuerysetMixin, ListView):
    model = Pedido
    template_name = "pedidos/caixa.html"
    context_object_name = "pedidos"

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .filter(status__in=ABERTOS)
            .select_related("mesa")
            .order_by("criado_em")
        )


class PedidoPagarView(CaixaAccessMixin, TenantQuerysetMixin, View):
    template_name = "pedidos/pedido_pagar.html"

    def _get_pedido(self, pk):
        return get_object_or_404(
            Pedido.objects.for_tenant(self.restaurante).select_related("mesa"), pk=pk
        )

    def _render(self, request, pedido, form):
        from django.shortcuts import render

        return render(
            request, self.template_name, {"pedido": pedido, "form": form}
        )

    def get(self, request, pk):
        pedido = self._get_pedido(pk)
        pedido.recalcular_totais(save=True)
        form = PagarPedidoForm(
            initial={"desconto": pedido.desconto, "valor_pago": pedido.total}
        )
        return self._render(request, pedido, form)

    def post(self, request, pk):
        pedido = self._get_pedido(pk)
        if pedido.pago:
            return redirect("pedidos:caixa")
        form = PagarPedidoForm(request.POST)
        if not form.is_valid():
            return self._render(request, pedido, form)

        pedido.desconto = form.cleaned_data["desconto"]
        total = pedido.recalcular_totais(save=True)  # subtotal - desconto (servidor)
        valor_pago = form.cleaned_data["valor_pago"]
        if valor_pago < total:
            form.add_error(
                "valor_pago",
                f"Valor pago (R$ {valor_pago}) é menor que o total (R$ {total}).",
            )
            return self._render(request, pedido, form)

        pedido.status = Pedido.Status.PAGO
        pedido.fechado_em = timezone.now()
        pedido.save(update_fields=["status", "fechado_em", "desconto", "subtotal", "total"])
        if pedido.mesa:
            pedido.mesa.status = Mesa.Status.LIVRE
            pedido.mesa.save(update_fields=["status"])

        # Registra o Pagamento (financeiro §2). Sem turno explícito no modelo:
        # a associação ao TurnoCaixa é temporal (ver financeiro.services).
        from apps.financeiro.models import Pagamento

        forma = form.cleaned_data.get("forma") or Pagamento.Forma.DINHEIRO
        Pagamento.objects.create(
            pedido=pedido,
            forma=forma,
            valor=total,
            troco=max(valor_pago - total, 0),
            usuario=request.user,
        )

        registrar_log(
            restaurante=self.restaurante,
            usuario=request.user,
            acao="fechar_pedido",
            entidade="Pedido",
            entidade_id=pedido.id,
            dados_depois={
                "total": str(total),
                "valor_pago": str(valor_pago),
                "desconto": str(pedido.desconto),
            },
        )
        return redirect("pedidos:caixa")
