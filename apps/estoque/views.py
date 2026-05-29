from __future__ import annotations

from django.db import transaction
from django.db.models import Count, ProtectedError
from django.http import HttpResponse
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from apps.core.mixins import PerfilRequiredMixin, TenantQuerysetMixin

from .forms import (
    AjusteEstoqueForm,
    CategoriaIngredienteForm,
    EntradaEstoqueForm,
    FornecedorForm,
    IngredienteForm,
)
from .models import (
    AjusteEstoque,
    CategoriaIngrediente,
    EntradaEstoque,
    Fornecedor,
    Ingrediente,
)

CHANGED_EVENT = "estoque:changed"


def _trigger_response() -> HttpResponse:
    """Resposta vazia que fecha o modal (#modal recebe innerHTML vazio) e dispara
    o evento HTMX que recarrega a tabela da listagem."""
    resp = HttpResponse("")
    resp["HX-Trigger"] = CHANGED_EVENT
    return resp


class EstoqueAccessMixin(PerfilRequiredMixin):
    """Acesso ao módulo de estoque: admin, gerente e almoxarife.

    ``PerfilRequiredMixin`` já herda de ``TenantMixin`` (define self.restaurante
    antes do dispatch), então não listamos ``TenantMixin`` separadamente."""

    perfis_permitidos = ("admin", "gerente", "almoxarife")


class HtmxFormMixin:
    """Comportamento comum de Create/Update via modal HTMX.

    - injeta ``restaurante`` no form;
    - define ``restaurante`` no objeto antes de salvar;
    - em sucesso, responde com o gatilho que recarrega a tabela;
    - em erro, o CreateView/UpdateView re-renderiza o modal com os erros (200).
    """

    titulo = ""
    set_usuario = False

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
        if self.set_usuario:
            obj.usuario = self.request.user
        obj.save()
        form.save_m2m()
        return _trigger_response()


# --------------------------------------------------------------------------- #
# Categorias de ingrediente
# --------------------------------------------------------------------------- #
class CategoriaIngredienteListView(
    EstoqueAccessMixin, TenantQuerysetMixin, ListView
):
    model = CategoriaIngrediente
    template_name = "estoque/categoria_list.html"
    context_object_name = "object_list"
    ordering = ["nome"]

    def get_queryset(self):
        return super().get_queryset().annotate(num_ingredientes=Count("ingredientes"))


class CategoriaIngredienteTabelaView(CategoriaIngredienteListView):
    template_name = "estoque/_categoria_tabela.html"


class CategoriaIngredienteCreateView(EstoqueAccessMixin, HtmxFormMixin, CreateView):
    model = CategoriaIngrediente
    form_class = CategoriaIngredienteForm
    template_name = "estoque/_form_modal.html"
    titulo = "Nova categoria"


class CategoriaIngredienteUpdateView(
    EstoqueAccessMixin, TenantQuerysetMixin, HtmxFormMixin, UpdateView
):
    model = CategoriaIngrediente
    form_class = CategoriaIngredienteForm
    template_name = "estoque/_form_modal.html"
    titulo = "Editar categoria"


class CategoriaIngredienteDeleteView(
    EstoqueAccessMixin, TenantQuerysetMixin, DeleteView
):
    model = CategoriaIngrediente
    template_name = "estoque/_confirm_delete.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["action_url"] = self.request.path
        return ctx

    def form_valid(self, form):
        # Categoria é FK SET_NULL em Ingrediente: a exclusão apenas desvincula.
        self.object = self.get_object()
        self.object.delete()
        return _trigger_response()


# --------------------------------------------------------------------------- #
# Ingredientes
# --------------------------------------------------------------------------- #
class IngredienteListView(EstoqueAccessMixin, TenantQuerysetMixin, ListView):
    model = Ingrediente
    template_name = "estoque/ingrediente_list.html"
    context_object_name = "object_list"
    ordering = ["nome"]

    def get_queryset(self):
        return super().get_queryset().select_related("categoria")


class IngredienteTabelaView(IngredienteListView):
    template_name = "estoque/_ingrediente_tabela.html"


class IngredienteCreateView(EstoqueAccessMixin, HtmxFormMixin, CreateView):
    model = Ingrediente
    form_class = IngredienteForm
    template_name = "estoque/_form_modal.html"
    titulo = "Novo ingrediente"


class IngredienteUpdateView(
    EstoqueAccessMixin, TenantQuerysetMixin, HtmxFormMixin, UpdateView
):
    model = Ingrediente
    form_class = IngredienteForm
    template_name = "estoque/_form_modal.html"
    titulo = "Editar ingrediente"


class IngredienteDeleteView(EstoqueAccessMixin, TenantQuerysetMixin, DeleteView):
    model = Ingrediente
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
            ctx["erro"] = "Não é possível excluir: há entradas, ajustes ou fichas vinculadas."
            return self.render_to_response(ctx)
        return _trigger_response()


# --------------------------------------------------------------------------- #
# Fornecedores
# --------------------------------------------------------------------------- #
class FornecedorListView(EstoqueAccessMixin, TenantQuerysetMixin, ListView):
    model = Fornecedor
    template_name = "estoque/fornecedor_list.html"
    context_object_name = "object_list"
    ordering = ["nome"]


class FornecedorTabelaView(FornecedorListView):
    template_name = "estoque/_fornecedor_tabela.html"


class FornecedorCreateView(EstoqueAccessMixin, HtmxFormMixin, CreateView):
    model = Fornecedor
    form_class = FornecedorForm
    template_name = "estoque/_form_modal.html"
    titulo = "Novo fornecedor"


class FornecedorUpdateView(
    EstoqueAccessMixin, TenantQuerysetMixin, HtmxFormMixin, UpdateView
):
    model = Fornecedor
    form_class = FornecedorForm
    template_name = "estoque/_form_modal.html"
    titulo = "Editar fornecedor"


class FornecedorDeleteView(EstoqueAccessMixin, TenantQuerysetMixin, DeleteView):
    model = Fornecedor
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
            ctx["erro"] = "Não é possível excluir: há entradas vinculadas."
            return self.render_to_response(ctx)
        return _trigger_response()


# --------------------------------------------------------------------------- #
# Entradas de estoque (ledger append-only: lista + nova)
# --------------------------------------------------------------------------- #
class EntradaEstoqueListView(EstoqueAccessMixin, TenantQuerysetMixin, ListView):
    model = EntradaEstoque
    template_name = "estoque/entrada_list.html"
    context_object_name = "object_list"
    ordering = ["-data_entrada"]

    def get_queryset(self):
        return super().get_queryset().select_related("ingrediente", "fornecedor")


class EntradaEstoqueTabelaView(EntradaEstoqueListView):
    template_name = "estoque/_entrada_tabela.html"


class EntradaEstoqueCreateView(EstoqueAccessMixin, HtmxFormMixin, CreateView):
    model = EntradaEstoque
    form_class = EntradaEstoqueForm
    template_name = "estoque/_form_modal.html"
    titulo = "Nova entrada de estoque"
    set_usuario = True
    # estoque_atual + CMP são atualizados pelo signal post_save (§3A).


# --------------------------------------------------------------------------- #
# Ajustes de estoque (ledger append-only: lista + novo)
# --------------------------------------------------------------------------- #
class AjusteEstoqueListView(EstoqueAccessMixin, TenantQuerysetMixin, ListView):
    model = AjusteEstoque
    template_name = "estoque/ajuste_list.html"
    context_object_name = "object_list"
    ordering = ["-criado_em"]

    def get_queryset(self):
        return super().get_queryset().select_related("ingrediente")


class AjusteEstoqueTabelaView(AjusteEstoqueListView):
    template_name = "estoque/_ajuste_tabela.html"


class AjusteEstoqueCreateView(EstoqueAccessMixin, HtmxFormMixin, CreateView):
    model = AjusteEstoque
    form_class = AjusteEstoqueForm
    template_name = "estoque/_form_modal.html"
    titulo = "Novo ajuste de estoque"

    def form_valid(self, form):
        ajuste = form.save(commit=False)
        ajuste.restaurante = self.restaurante
        ajuste.usuario = self.request.user
        with transaction.atomic():
            ing = Ingrediente.objects.select_for_update().get(
                pk=ajuste.ingrediente_id
            )
            ajuste.qtd_anterior = ing.estoque_atual
            ajuste.save()
            ing.estoque_atual = ajuste.qtd_nova
            ing.save(update_fields=["estoque_atual"])
        return _trigger_response()
