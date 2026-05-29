from __future__ import annotations

from django.db.models import Count, ProtectedError
from django.http import HttpResponse
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from apps.core.mixins import PerfilRequiredMixin, TenantQuerysetMixin

from .forms import CategoriaPratoForm, PratoForm
from .models import CategoriaPrato, Prato

CHANGED_EVENT = "cardapio:changed"


def _trigger_response() -> HttpResponse:
    """Resposta vazia que fecha o modal (#modal recebe innerHTML vazio) e dispara
    o evento HTMX que recarrega a tabela da listagem."""
    resp = HttpResponse("")
    resp["HX-Trigger"] = CHANGED_EVENT
    return resp


class CardapioAccessMixin(PerfilRequiredMixin):
    """Cardápio: escrita restrita a admin e gerente (§5).

    ``PerfilRequiredMixin`` já herda de ``TenantMixin`` (define self.restaurante
    antes do dispatch), então não listamos ``TenantMixin`` separadamente."""

    perfis_permitidos = ("admin", "gerente")


class HtmxFormMixin:
    """Comportamento comum de Create/Update via modal HTMX."""

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
        form.save_m2m()
        return _trigger_response()


# --------------------------------------------------------------------------- #
# Categorias de prato
# --------------------------------------------------------------------------- #
class CategoriaPratoListView(CardapioAccessMixin, TenantQuerysetMixin, ListView):
    model = CategoriaPrato
    template_name = "cardapio/categoria_prato_list.html"
    context_object_name = "object_list"

    def get_queryset(self):
        return super().get_queryset().annotate(num_pratos=Count("pratos"))


class CategoriaPratoTabelaView(CategoriaPratoListView):
    template_name = "cardapio/_categoria_prato_tabela.html"


class CategoriaPratoCreateView(CardapioAccessMixin, HtmxFormMixin, CreateView):
    model = CategoriaPrato
    form_class = CategoriaPratoForm
    template_name = "estoque/_form_modal.html"
    titulo = "Nova categoria de prato"


class CategoriaPratoUpdateView(
    CardapioAccessMixin, TenantQuerysetMixin, HtmxFormMixin, UpdateView
):
    model = CategoriaPrato
    form_class = CategoriaPratoForm
    template_name = "estoque/_form_modal.html"
    titulo = "Editar categoria de prato"


class CategoriaPratoDeleteView(
    CardapioAccessMixin, TenantQuerysetMixin, DeleteView
):
    model = CategoriaPrato
    template_name = "estoque/_confirm_delete.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["action_url"] = self.request.path
        return ctx

    def form_valid(self, form):
        # Prato.categoria é FK PROTECT: bloqueia exclusão se houver pratos.
        self.object = self.get_object()
        try:
            self.object.delete()
        except ProtectedError:
            ctx = self.get_context_data(object=self.object)
            ctx["erro"] = "Não é possível excluir: há pratos nesta categoria."
            return self.render_to_response(ctx)
        return _trigger_response()


# --------------------------------------------------------------------------- #
# Pratos
# --------------------------------------------------------------------------- #
class PratoListView(CardapioAccessMixin, TenantQuerysetMixin, ListView):
    model = Prato
    template_name = "cardapio/prato_list.html"
    context_object_name = "object_list"
    ordering = ["categoria__ordem", "nome"]

    def get_queryset(self):
        return super().get_queryset().select_related("categoria", "ficha")


class PratoTabelaView(PratoListView):
    template_name = "cardapio/_prato_tabela.html"


class PratoFormMixin(HtmxFormMixin):
    """Salva o prato e recalcula custo/margem a partir da ficha.

    O signal ``Prato.pre_save`` (§3D) registra ``HistoricoPreco`` quando o
    ``preco_venda`` muda; por isso anexamos o usuário responsável em
    ``_usuario_alteracao`` antes de salvar."""

    def form_valid(self, form):
        prato = form.save(commit=False)
        prato.restaurante = self.restaurante
        prato._usuario_alteracao = self.request.user
        prato.save()  # dispara pre_save -> HistoricoPreco se preço mudou
        prato.atualizar_custo(save=True)  # custo_atual + margem a partir da ficha
        return _trigger_response()


class PratoCreateView(CardapioAccessMixin, PratoFormMixin, CreateView):
    model = Prato
    form_class = PratoForm
    template_name = "estoque/_form_modal.html"
    titulo = "Novo prato"


class PratoUpdateView(
    CardapioAccessMixin, TenantQuerysetMixin, PratoFormMixin, UpdateView
):
    model = Prato
    form_class = PratoForm
    template_name = "estoque/_form_modal.html"
    titulo = "Editar prato"


class PratoDeleteView(CardapioAccessMixin, TenantQuerysetMixin, DeleteView):
    model = Prato
    template_name = "estoque/_confirm_delete.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["action_url"] = self.request.path
        return ctx

    def form_valid(self, form):
        self.object = self.get_object()
        try:
            self.object.delete()
        except ProtectedError:
            ctx = self.get_context_data(object=self.object)
            ctx["erro"] = "Não é possível excluir: há itens de pedido vinculados a este prato."
            return self.render_to_response(ctx)
        return _trigger_response()
