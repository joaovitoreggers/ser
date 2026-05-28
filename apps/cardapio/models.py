from __future__ import annotations

import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.core.models import TenantModel


class CategoriaPrato(TenantModel):
    nome = models.CharField(max_length=100)
    ordem = models.PositiveIntegerField(default=0)
    hora_inicio = models.TimeField(null=True, blank=True)
    hora_fim = models.TimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Categoria de Prato"
        verbose_name_plural = "Categorias de Prato"
        ordering = ["ordem", "nome"]

    def __str__(self) -> str:
        return self.nome


class Prato(TenantModel):
    ficha = models.OneToOneField(
        "fichas.FichaTecnica", on_delete=models.PROTECT, related_name="prato"
    )
    categoria = models.ForeignKey(
        CategoriaPrato, on_delete=models.PROTECT, related_name="pratos"
    )
    nome = models.CharField(max_length=200)
    preco_venda = models.DecimalField(max_digits=10, decimal_places=2)
    custo_atual = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    margem_lucro = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    disponivel = models.BooleanField(default=True)
    motivo_indisponivel = models.TextField(blank=True)

    class Meta:
        verbose_name = "Prato"
        verbose_name_plural = "Pratos"
        indexes = [
            models.Index(
                fields=["restaurante", "categoria"],
                name="idx_prato_disponivel",
                condition=Q(disponivel=True),
            ),
        ]

    def atualizar_custo(self, *, save: bool = True) -> Decimal:
        """custo_atual = ficha.custo_porcao;
        margem_lucro = (preco_venda - custo_atual) / preco_venda × 100."""
        self.custo_atual = self.ficha.custo_porcao
        if self.preco_venda and self.preco_venda > 0:
            margem = (self.preco_venda - self.custo_atual) / self.preco_venda * 100
            self.margem_lucro = margem.quantize(Decimal("0.01"))
        else:
            self.margem_lucro = Decimal("0")
        if save:
            self.save(update_fields=["custo_atual", "margem_lucro"])
        return self.margem_lucro

    def __str__(self) -> str:
        return self.nome


class HistoricoPreco(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    prato = models.ForeignKey(
        Prato, on_delete=models.CASCADE, related_name="historico_precos"
    )
    preco_anterior = models.DecimalField(max_digits=10, decimal_places=2)
    preco_novo = models.DecimalField(max_digits=10, decimal_places=2)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="alteracoes_preco",
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Histórico de Preço"
        verbose_name_plural = "Históricos de Preço"
        ordering = ["-criado_em"]

    def __str__(self) -> str:
        return f"{self.prato}: {self.preco_anterior} -> {self.preco_novo}"
