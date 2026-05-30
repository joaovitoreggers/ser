from __future__ import annotations

import uuid
from decimal import Decimal

from django.db import models

from apps.core.models import TenantModel


class FichaTecnica(TenantModel):
    nome = models.CharField(max_length=200)
    rendimento = models.PositiveIntegerField(default=1)
    custo_total = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    custo_porcao = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    versao = models.PositiveIntegerField(default=1)
    ativo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Receita"
        verbose_name_plural = "Receitas"

    def recalcular_custo(self, *, save: bool = True) -> Decimal:
        """custo_total = Σ(fi.quantidade × ingrediente.custo_unitario);
        custo_porcao = custo_total / rendimento."""
        total = Decimal("0")
        for fi in self.ingredientes.select_related("ingrediente"):
            total += fi.quantidade * fi.ingrediente.custo_unitario
        self.custo_total = total
        rendimento = self.rendimento or 1
        self.custo_porcao = (total / rendimento).quantize(Decimal("0.0001"))
        if save:
            self.save(update_fields=["custo_total", "custo_porcao"])
        return self.custo_porcao

    def __str__(self) -> str:
        return self.nome


class FichaIngrediente(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ficha = models.ForeignKey(
        FichaTecnica, on_delete=models.CASCADE, related_name="ingredientes"
    )
    ingrediente = models.ForeignKey(
        "estoque.Ingrediente", on_delete=models.PROTECT, related_name="usos_em_fichas"
    )
    quantidade = models.DecimalField(max_digits=12, decimal_places=4)
    unidade = models.CharField(max_length=5)
    principal = models.BooleanField(default=True)
    custo_snapshot = models.DecimalField(max_digits=12, decimal_places=4, default=0)

    class Meta:
        verbose_name = "Ingrediente da Receita"
        verbose_name_plural = "Ingredientes da Receita"

    def __str__(self) -> str:
        return f"{self.quantidade}{self.unidade} {self.ingrediente}"


class FichaTecnicaVersao(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ficha = models.ForeignKey(
        FichaTecnica, on_delete=models.CASCADE, related_name="versoes"
    )
    versao = models.PositiveIntegerField()
    dados = models.JSONField(default=dict)

    class Meta:
        verbose_name = "Versão de Receita"
        verbose_name_plural = "Versões de Receita"

    def __str__(self) -> str:
        return f"{self.ficha} v{self.versao}"
