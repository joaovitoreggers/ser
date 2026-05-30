from __future__ import annotations

from django import forms

from apps.fichas.models import FichaTecnica

from .models import CategoriaPrato, Prato

INPUT_CLASS = "w-full border border-gray-300 rounded px-3 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-500"
CHECKBOX_CLASS = "h-4 w-4 rounded border-gray-300 text-indigo-600"


class TenantModelForm(forms.ModelForm):
    """ModelForm base multi-tenant do cardápio.

    Recebe ``restaurante`` (do usuário logado), aplica estilo Tailwind aos
    widgets e restringe os querysets de FKs ao tenant via ``_scope_tenant_fks``.
    O campo ``restaurante`` nunca é exposto — é definido na view.
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


class CategoriaPratoForm(TenantModelForm):
    class Meta:
        model = CategoriaPrato
        fields = ["nome", "ordem", "hora_inicio", "hora_fim"]
        labels = {
            "hora_inicio": "Disponível a partir de",
            "hora_fim": "Disponível até",
        }
        widgets = {
            "hora_inicio": forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
            "hora_fim": forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for nome in ("hora_inicio", "hora_fim"):
            self.fields[nome].input_formats = ["%H:%M"]


class PratoForm(TenantModelForm):
    """Cadastro de prato. ``custo_atual`` e ``margem_lucro`` são calculados
    a partir da ficha técnica (``atualizar_custo``) e nunca editados aqui."""

    class Meta:
        model = Prato
        fields = [
            "nome",
            "categoria",
            "ficha",
            "preco_venda",
            "disponivel",
            "motivo_indisponivel",
        ]
        labels = {
            "ficha": "Receita",
        }
        widgets = {
            "motivo_indisponivel": forms.Textarea(attrs={"rows": 2}),
        }

    def _scope_tenant_fks(self) -> None:
        if self.restaurante is None:
            return
        self.fields["categoria"].queryset = CategoriaPrato.objects.for_tenant(
            self.restaurante
        )
        # Ficha é OneToOne: só fichas ativas ainda não vinculadas a outro prato
        # (mantendo a ficha do próprio prato em edição).
        fichas = FichaTecnica.objects.for_tenant(self.restaurante).filter(ativo=True)
        usadas = Prato.objects.for_tenant(self.restaurante)
        if self.instance.pk:
            usadas = usadas.exclude(pk=self.instance.pk)
        self.fields["ficha"].queryset = fichas.exclude(
            pk__in=usadas.values("ficha_id")
        )
