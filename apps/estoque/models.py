from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.core.models import TenantManager, TenantModel


class UnidadeMedida(models.TextChoices):
    GRAMA = "g", "Grama"
    QUILO = "kg", "Quilograma"
    MILILITRO = "ml", "Mililitro"
    LITRO = "L", "Litro"
    UNIDADE = "un", "Unidade"


class CategoriaIngrediente(TenantModel):
    nome = models.CharField(max_length=100)

    class Meta:
        verbose_name = "Categoria de Ingrediente"
        verbose_name_plural = "Categorias de Ingrediente"
        constraints = [
            models.UniqueConstraint(
                fields=["restaurante", "nome"],
                name="uniq_categoria_ingrediente_por_restaurante",
            )
        ]

    def __str__(self) -> str:
        return self.nome


class Ingrediente(TenantModel):
    categoria = models.ForeignKey(
        CategoriaIngrediente,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ingredientes",
    )
    nome = models.CharField(max_length=200)
    unidade_medida = models.CharField(max_length=3, choices=UnidadeMedida.choices)
    estoque_atual = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    estoque_minimo = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    custo_unitario = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    ativo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Ingrediente"
        verbose_name_plural = "Ingredientes"
        indexes = [
            models.Index(
                fields=["restaurante"],
                name="idx_ingrediente_ativo",
                condition=Q(ativo=True),
            ),
        ]

    @property
    def abaixo_minimo(self) -> bool:
        return self.estoque_atual <= self.estoque_minimo

    def __str__(self) -> str:
        return f"{self.nome} ({self.unidade_medida})"


class Fornecedor(TenantModel):
    nome = models.CharField(max_length=200)
    cnpj = models.CharField(max_length=18, blank=True)
    ativo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Fornecedor"
        verbose_name_plural = "Fornecedores"

    def __str__(self) -> str:
        return self.nome


class EntradaEstoque(TenantModel):
    ingrediente = models.ForeignKey(
        Ingrediente, on_delete=models.PROTECT, related_name="entradas"
    )
    fornecedor = models.ForeignKey(
        Fornecedor,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="entradas",
    )
    quantidade = models.DecimalField(max_digits=12, decimal_places=3)
    custo_unitario = models.DecimalField(max_digits=12, decimal_places=4)
    data_entrada = models.DateField()
    nota_fiscal = models.CharField(max_length=60, blank=True)
    validade = models.DateField(null=True, blank=True)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="entradas_estoque",
    )

    class Meta:
        verbose_name = "Entrada de Estoque"
        verbose_name_plural = "Entradas de Estoque"

    def __str__(self) -> str:
        return f"Entrada {self.quantidade} de {self.ingrediente}"


class AjusteEstoque(TenantModel):
    class Motivo(models.TextChoices):
        INVENTARIO = "inventario", "Inventário"
        AVARIA = "avaria", "Avaria"
        VENCIMENTO = "vencimento", "Vencimento"
        ROUBO = "roubo", "Roubo"
        OUTROS = "outros", "Outros"

    ingrediente = models.ForeignKey(
        Ingrediente, on_delete=models.PROTECT, related_name="ajustes"
    )
    qtd_anterior = models.DecimalField(max_digits=12, decimal_places=3)
    qtd_nova = models.DecimalField(max_digits=12, decimal_places=3)
    motivo = models.CharField(max_length=20, choices=Motivo.choices)
    descricao = models.TextField(blank=True)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="ajustes_estoque",
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Ajuste de Estoque"
        verbose_name_plural = "Ajustes de Estoque"

    def __str__(self) -> str:
        return f"Ajuste {self.ingrediente}: {self.qtd_anterior} -> {self.qtd_nova}"
