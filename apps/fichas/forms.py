from __future__ import annotations

from django import forms
from django.forms import inlineformset_factory

from apps.estoque.models import Ingrediente, UnidadeMedida

from .models import FichaIngrediente, FichaTecnica

INPUT_CLASS = "w-full border border-gray-300 rounded px-3 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-500"
CHECKBOX_CLASS = "h-4 w-4 rounded border-gray-300 text-indigo-600"


def _aplicar_estilo(form: forms.BaseForm) -> None:
    for field in form.fields.values():
        widget = field.widget
        base = CHECKBOX_CLASS if isinstance(widget, forms.CheckboxInput) else INPUT_CLASS
        existing = widget.attrs.get("class", "")
        widget.attrs["class"] = f"{existing} {base}".strip()


class FichaTecnicaForm(forms.ModelForm):
    """Cabeçalho da ficha. ``custo_total``/``custo_porcao`` são calculados
    (recalcular_custo) e nunca editados diretamente."""

    class Meta:
        model = FichaTecnica
        fields = ["nome", "rendimento", "ativo"]

    def __init__(self, *args, restaurante=None, **kwargs):
        self.restaurante = restaurante
        super().__init__(*args, **kwargs)
        _aplicar_estilo(self)


class FichaIngredienteForm(forms.ModelForm):
    class Meta:
        model = FichaIngrediente
        fields = ["ingrediente", "quantidade", "unidade", "principal"]
        widgets = {"unidade": forms.Select(choices=UnidadeMedida.choices)}

    def __init__(self, *args, restaurante=None, **kwargs):
        self.restaurante = restaurante
        super().__init__(*args, **kwargs)
        if restaurante is not None:
            self.fields["ingrediente"].queryset = Ingrediente.objects.for_tenant(
                restaurante
            ).filter(ativo=True)
        _aplicar_estilo(self)


FichaIngredienteFormSet = inlineformset_factory(
    FichaTecnica,
    FichaIngrediente,
    form=FichaIngredienteForm,
    extra=1,
    can_delete=True,
    min_num=1,
    validate_min=True,
)
