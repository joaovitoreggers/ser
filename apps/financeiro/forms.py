from __future__ import annotations

from decimal import Decimal

from django import forms

from .models import MovimentacaoCaixa, TurnoCaixa

INPUT_CLASS = "w-full border border-gray-300 rounded px-3 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-500"


def _style(form: forms.BaseForm) -> None:
    for field in form.fields.values():
        existing = field.widget.attrs.get("class", "")
        field.widget.attrs["class"] = f"{existing} {INPUT_CLASS}".strip()


class AbrirTurnoForm(forms.ModelForm):
    class Meta:
        model = TurnoCaixa
        fields = ["valor_abertura"]
        widgets = {
            "valor_abertura": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
        }
        labels = {"valor_abertura": "Valor de abertura (R$)"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _style(self)


class FecharTurnoForm(forms.ModelForm):
    class Meta:
        model = TurnoCaixa
        fields = ["valor_fechamento"]
        widgets = {
            "valor_fechamento": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
        }
        labels = {"valor_fechamento": "Valor contado na gaveta (R$)"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["valor_fechamento"].required = True
        _style(self)


class MovimentacaoForm(forms.ModelForm):
    """Sangria/suprimento. A sangria (retirada) exige PIN de gerente/admin,
    validado na view (autorizado_por)."""

    pin = forms.CharField(
        required=False,
        widget=forms.PasswordInput(attrs={"inputmode": "numeric"}),
        label="PIN do gerente/admin (sangria)",
    )

    class Meta:
        model = MovimentacaoCaixa
        fields = ["tipo", "valor", "motivo"]
        widgets = {
            "valor": forms.NumberInput(attrs={"step": "0.01", "min": "0.01"}),
            "motivo": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _style(self)

    def clean_valor(self):
        valor = self.cleaned_data["valor"]
        if valor is None or valor <= Decimal("0"):
            raise forms.ValidationError("O valor deve ser maior que zero.")
        return valor
