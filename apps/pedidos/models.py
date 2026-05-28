from __future__ import annotations

import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from apps.core.models import TenantModel


class Mesa(TenantModel):
    class Status(models.TextChoices):
        LIVRE = "livre", "Livre"
        OCUPADA = "ocupada", "Ocupada"
        AGUARDANDO_PEDIDO = "aguardando_pedido", "Aguardando Pedido"
        EM_ATENDIMENTO = "em_atendimento", "Em Atendimento"
        AGUARDANDO_PAGAMENTO = "aguardando_pagamento", "Aguardando Pagamento"

    numero = models.PositiveIntegerField()
    status = models.CharField(
        max_length=24, choices=Status.choices, default=Status.LIVRE
    )

    class Meta:
        verbose_name = "Mesa"
        verbose_name_plural = "Mesas"
        constraints = [
            models.UniqueConstraint(
                fields=["restaurante", "numero"], name="uniq_mesa_numero_por_restaurante"
            )
        ]

    def __str__(self) -> str:
        return f"Mesa {self.numero}"


class Pedido(TenantModel):
    class Tipo(models.TextChoices):
        MESA = "mesa", "Mesa"
        BALCAO = "balcao", "Balcão"
        DELIVERY = "delivery", "Delivery"

    class Status(models.TextChoices):
        ABERTO = "aberto", "Aberto"
        EM_ATENDIMENTO = "em_atendimento", "Em Atendimento"
        AGUARDANDO_PAGAMENTO = "aguardando_pagamento", "Aguardando Pagamento"
        PAGO = "pago", "Pago"
        FIADO = "fiado", "Fiado"
        CANCELADO = "cancelado", "Cancelado"

    mesa = models.ForeignKey(
        Mesa, on_delete=models.PROTECT, null=True, blank=True, related_name="pedidos"
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="pedidos",
    )
    tipo = models.CharField(max_length=10, choices=Tipo.choices, default=Tipo.MESA)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.ABERTO
    )
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    desconto = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    criado_em = models.DateTimeField(auto_now_add=True)
    fechado_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Pedido"
        verbose_name_plural = "Pedidos"
        indexes = [
            models.Index(
                fields=["restaurante", "status"], name="idx_pedido_rest_status"
            ),
            models.Index(
                fields=["mesa"],
                name="idx_pedido_mesa_aberto",
                condition=~Q(status__in=["pago", "cancelado"]),
            ),
        ]

    @property
    def pago(self) -> bool:
        return self.status == self.Status.PAGO

    def recalcular_totais(self, *, save: bool = True) -> Decimal:
        """Server-side totals; client payload is ignored.
        subtotal = Σ item.subtotal (não cancelados); total = subtotal − desconto."""
        subtotal = Decimal("0")
        for item in self.itens.all():
            if item.status != ItemPedido.Status.CANCELADO:
                subtotal += item.subtotal
        self.subtotal = subtotal
        self.total = subtotal - self.desconto
        if save:
            self.save(update_fields=["subtotal", "total"])
        return self.total

    def __str__(self) -> str:
        return f"Pedido {self.id} ({self.get_status_display()})"


class ItemPedido(models.Model):
    class Status(models.TextChoices):
        AGUARDANDO = "aguardando", "Aguardando"
        EM_PREPARO = "em_preparo", "Em Preparo"
        PRONTO = "pronto", "Pronto"
        ENTREGUE = "entregue", "Entregue"
        CANCELADO = "cancelado", "Cancelado"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE, related_name="itens")
    prato = models.ForeignKey(
        "cardapio.Prato", on_delete=models.PROTECT, related_name="itens_pedido"
    )
    quantidade = models.PositiveIntegerField(default=1)
    preco_unitario = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    custo_unitario = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.AGUARDANDO
    )
    enviado_em = models.DateTimeField(null=True, blank=True)
    pronto_em = models.DateTimeField(null=True, blank=True)
    motivo_cancelamento = models.TextField(blank=True)

    class Meta:
        verbose_name = "Item de Pedido"
        verbose_name_plural = "Itens de Pedido"
        indexes = [
            models.Index(fields=["pedido", "status"], name="idx_item_pedido_status"),
        ]

    def clean(self) -> None:
        # §4.1 — pedido pago é somente leitura.
        if self.pedido_id and self.pedido.status == Pedido.Status.PAGO:
            raise ValidationError(
                "Pedido pago é somente leitura: itens não podem ser alterados."
            )

    def save(self, *args, **kwargs) -> None:
        if self._state.adding:
            # §4.2 — congela snapshot de preço/custo na criação.
            self.preco_unitario = self.prato.preco_venda
            self.custo_unitario = self.prato.custo_atual
        self.subtotal = (self.preco_unitario * self.quantidade).quantize(
            Decimal("0.01")
        )
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.quantidade}x {self.prato} ({self.get_status_display()})"
