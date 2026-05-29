from __future__ import annotations

from django import forms
from django.utils import timezone

from .models import (
    AjusteEstoque,
    CategoriaIngrediente,
    EntradaEstoque,
    Fornecedor,
    Ingrediente,
)

INPUT_CLASS = "w-full border border-gray-300 rounded px-3 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-500"
CHECKBOX_CLASS = "h-4 w-4 rounded border-gray-300 text-indigo-600"


class TenantModelForm(forms.ModelForm):
    """ModelForm base multi-tenant.

    Recebe ``restaurante`` (do usuário logado), aplica estilo Tailwind aos
    widgets e restringe os querysets de FKs ao tenant via ``_scope_tenant_fks``.
    O campo ``restaurante`` nunca é exposto no formulário — é definido na view.
    """

    def __init__(self, *args, restaurante=None, **kwargs):
        self.restaurante = restaurante
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            base = CHECKBOX_CLASS if isinstance(widget, forms.CheckboxInput) else INPUT_CLASS
            existing = widget.attrs.get("class", "")
            widget.attrs["class"] = f"{existing} {base}".strip()
        self._scope_tenant_fks()

    def _scope_tenant_fks(self) -> None:  # pragma: no cover - sobrescrito
        pass


class CategoriaIngredienteForm(TenantModelForm):
    class Meta:
        model = CategoriaIngrediente
        fields = ["nome"]

    def clean_nome(self):
        nome = self.cleaned_data["nome"]
        if self.restaurante is not None:
            qs = CategoriaIngrediente.objects.for_tenant(self.restaurante).filter(
                nome__iexact=nome
            )
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError("Já existe uma categoria com esse nome.")
        return nome


class IngredienteForm(TenantModelForm):
    class Meta:
        model = Ingrediente
        fields = [
            "nome",
            "categoria",
            "unidade_medida",
            "estoque_minimo",
            "custo_unitario",
            "ativo",
        ]

    def _scope_tenant_fks(self) -> None:
        if self.restaurante is not None:
            self.fields["categoria"].queryset = CategoriaIngrediente.objects.for_tenant(
                self.restaurante
            )


class FornecedorForm(TenantModelForm):
    class Meta:
        model = Fornecedor
        fields = ["nome", "cnpj", "ativo"]


class EntradaEstoqueForm(TenantModelForm):
    class Meta:
        model = EntradaEstoque
        fields = [
            "ingrediente",
            "fornecedor",
            "quantidade",
            "custo_unitario",
            "data_entrada",
            "nota_fiscal",
        ]
        widgets = {
            "data_entrada": forms.DateInput(
                attrs={"type": "date"}, format="%Y-%m-%d"
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["data_entrada"].input_formats = ["%Y-%m-%d"]
        if not self.instance.pk and not self.initial.get("data_entrada"):
            self.initial["data_entrada"] = timezone.localdate()

    def _scope_tenant_fks(self) -> None:
        if self.restaurante is not None:
            self.fields["ingrediente"].queryset = Ingrediente.objects.for_tenant(
                self.restaurante
            ).filter(ativo=True)
            self.fields["fornecedor"].queryset = Fornecedor.objects.for_tenant(
                self.restaurante
            ).filter(ativo=True)


class AjusteEstoqueForm(TenantModelForm):
    """Ajuste de inventário: o usuário informa a quantidade real contada
    (``qtd_nova``). A ``qtd_anterior`` é capturada na view a partir do estoque
    atual do ingrediente, sob lock de linha, no momento do ajuste."""

    class Meta:
        model = AjusteEstoque
        fields = ["ingrediente", "qtd_nova", "motivo", "descricao"]
        labels = {
            "qtd_nova": "Nova quantidade (contagem real)",
            "descricao": "Descrição / observação",
        }

    def _scope_tenant_fks(self) -> None:
        if self.restaurante is not None:
            self.fields["ingrediente"].queryset = Ingrediente.objects.for_tenant(
                self.restaurante
            ).filter(ativo=True)
