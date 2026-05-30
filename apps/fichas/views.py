from __future__ import annotations

from django.db import transaction
from django.db.models import ProtectedError
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from apps.core.mixins import PerfilRequiredMixin, TenantQuerysetMixin

from .forms import FichaIngredienteFormSet, FichaTecnicaForm
from .models import FichaTecnica

FORMSET_PREFIX = "ingredientes"


class FichasAccessMixin(PerfilRequiredMixin):
    """Fichas técnicas: acesso de admin e gerente (§5)."""

    perfis_permitidos = ("admin", "gerente")


class FichaTecnicaListView(FichasAccessMixin, TenantQuerysetMixin, ListView):
    model = FichaTecnica
    template_name = "fichas/ficha_list.html"
    context_object_name = "object_list"
    ordering = ["nome"]


class FichaFormMixin:
    """Create/Update de FichaTecnica com o inline formset de ingredientes.

    Salva o cabeçalho + linhas numa transação, grava ``custo_snapshot`` de cada
    linha a partir do custo atual do ingrediente e chama ``recalcular_custo()``
    (que dispara, via signal, a cascata de custo do Prato §3B)."""

    model = FichaTecnica
    form_class = FichaTecnicaForm
    template_name = "fichas/ficha_form.html"
    success_url = reverse_lazy("fichas:ficha_list")
    titulo = ""

    # Sobrescrito nas subclasses (None no create; objeto no update).
    def carregar_objeto(self):
        raise NotImplementedError

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["restaurante"] = self.restaurante
        return kwargs

    def build_formset(self, instance):
        return FichaIngredienteFormSet(
            self.request.POST if self.request.method == "POST" else None,
            instance=instance,
            prefix=FORMSET_PREFIX,
            form_kwargs={"restaurante": self.restaurante},
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.setdefault("formset", self.build_formset(self.object))
        ctx["titulo"] = self.titulo
        return ctx

    def post(self, request, *args, **kwargs):
        self.object = self.carregar_objeto()
        form = self.get_form()
        formset = self.build_formset(self.object)
        if form.is_valid() and formset.is_valid():
            return self.salvar(form, formset)
        return self.render_to_response(
            self.get_context_data(form=form, formset=formset)
        )

    def salvar(self, form, formset):
        with transaction.atomic():
            ficha = form.save(commit=False)
            ficha.restaurante = self.restaurante
            ficha.save()
            formset.instance = ficha
            linhas = formset.save(commit=False)
            for linha in linhas:
                linha.custo_snapshot = linha.ingrediente.custo_unitario
                linha.save()
            for obj in formset.deleted_objects:
                obj.delete()
            ficha.recalcular_custo(save=True)
        self.object = ficha
        return redirect(self.get_success_url())


class FichaTecnicaCreateView(FichasAccessMixin, FichaFormMixin, CreateView):
    titulo = "Nova receita"

    def carregar_objeto(self):
        return None


class FichaTecnicaUpdateView(
    FichasAccessMixin, TenantQuerysetMixin, FichaFormMixin, UpdateView
):
    titulo = "Editar receita"

    def carregar_objeto(self):
        return self.get_object()


class FichaTecnicaDeleteView(FichasAccessMixin, TenantQuerysetMixin, DeleteView):
    model = FichaTecnica
    template_name = "fichas/ficha_confirm_delete.html"
    success_url = reverse_lazy("fichas:ficha_list")

    def form_valid(self, form):
        self.object = self.get_object()
        try:
            self.object.delete()
        except ProtectedError:
            return self.render_to_response(
                self.get_context_data(
                    object=self.object,
                    erro="Não é possível excluir: há um prato vinculado a esta receita.",
                )
            )
        return redirect(self.get_success_url())
