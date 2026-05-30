from __future__ import annotations

from decimal import Decimal

from django import forms

from apps.cardapio.models import Prato

from .models import ItemPedido, Mesa

INPUT_CLASS = "w-full border border-gray-300 rounded px-3 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-500"
CHECKBOX_CLASS = "h-4 w-4 rounded border-gray-300 text-indigo-600"


class TenantModelForm(forms.ModelForm):
    """ModelForm base multi-tenant de pedidos (estilo Tailwind + escopo de FKs)."""

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


class MesaForm(TenantModelForm):
    class Meta:
        model = Mesa
        fields = ["numero", "status"]

    def clean_numero(self):
        numero = self.cleaned_data["numero"]
        if self.restaurante is not None:
            qs = Mesa.objects.for_tenant(self.restaurante).filter(numero=numero)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError("Já existe uma mesa com esse número.")
        return numero


class ItemPedidoForm(TenantModelForm):
    """Adiciona um item ao pedido. O snapshot de preço/custo é congelado no
    ``ItemPedido.save()`` (§4.2); aqui só escolhemos prato e quantidade."""

    class Meta:
        model = ItemPedido
        fields = ["prato", "quantidade"]

    def _scope_tenant_fks(self) -> None:
        if self.restaurante is not None:
            self.fields["prato"].queryset = Prato.objects.for_tenant(
                self.restaurante
            ).filter(disponivel=True)

    def clean_quantidade(self):
        qtd = self.cleaned_data["quantidade"]
        if qtd < 1:
            raise forms.ValidationError("A quantidade deve ser pelo menos 1.")
        return qtd


class CancelarItemForm(forms.Form):
    """Cancelamento de item (§4.4). Sempre exige motivo; o PIN de um aprovador
    (gerente/admin) é validado na view quando o item já saiu de 'aguardando'."""

    motivo = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 2, "class": INPUT_CLASS}),
        label="Motivo do cancelamento",
    )
    pin = forms.CharField(
        required=False,
        widget=forms.PasswordInput(attrs={"class": INPUT_CLASS, "inputmode": "numeric"}),
        label="PIN do gerente/admin",
    )


class PagarPedidoForm(forms.Form):
    """Fechamento de pedido (§4.3): valor pago deve cobrir o total."""

    FORMA_CHOICES = [
        ("dinheiro", "Dinheiro"),
        ("debito", "Débito"),
        ("credito", "Crédito"),
        ("pix", "Pix"),
        ("voucher", "Voucher"),
    ]

    forma = forms.ChoiceField(
        choices=FORMA_CHOICES,
        required=False,
        initial="dinheiro",
        widget=forms.Select(attrs={"class": INPUT_CLASS}),
        label="Forma de pagamento",
    )
    desconto = forms.DecimalField(
        min_value=Decimal("0"),
        max_digits=10,
        decimal_places=2,
        initial=Decimal("0"),
        widget=forms.NumberInput(attrs={"class": INPUT_CLASS, "step": "0.01"}),
        label="Desconto (R$)",
    )
    valor_pago = forms.DecimalField(
        min_value=Decimal("0"),
        max_digits=10,
        decimal_places=2,
        widget=forms.NumberInput(attrs={"class": INPUT_CLASS, "step": "0.01"}),
        label="Valor pago (R$)",
    )
