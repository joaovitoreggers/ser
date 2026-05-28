from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models

from apps.core.models import TenantModel


class TurnoCaixa(TenantModel):
    class Status(models.TextChoices):
        ABERTO = "aberto", "Aberto"
        FECHADO = "fechado", "Fechado"

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="turnos_caixa",
    )
    valor_abertura = models.DecimalField(max_digits=10, decimal_places=2)
    valor_fechamento = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.ABERTO
    )
    aberto_em = models.DateTimeField(auto_now_add=True)
    fechado_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Turno de Caixa"
        verbose_name_plural = "Turnos de Caixa"

    def __str__(self) -> str:
        return f"Turno {self.id} ({self.get_status_display()})"


class MovimentacaoCaixa(models.Model):
    class Tipo(models.TextChoices):
        SANGRIA = "sangria", "Sangria"
        SUPRIMENTO = "suprimento", "Suprimento"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    turno = models.ForeignKey(
        TurnoCaixa, on_delete=models.PROTECT, related_name="movimentacoes"
    )
    tipo = models.CharField(max_length=10, choices=Tipo.choices)
    valor = models.DecimalField(max_digits=10, decimal_places=2)
    motivo = models.TextField(blank=True)
    autorizado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="movimentacoes_autorizadas",
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="movimentacoes",
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Movimentação de Caixa"
        verbose_name_plural = "Movimentações de Caixa"

    def __str__(self) -> str:
        return f"{self.get_tipo_display()} {self.valor}"


class Pagamento(models.Model):
    class Forma(models.TextChoices):
        DINHEIRO = "dinheiro", "Dinheiro"
        DEBITO = "debito", "Débito"
        CREDITO = "credito", "Crédito"
        PIX = "pix", "Pix"
        VOUCHER = "voucher", "Voucher"
        FIADO = "fiado", "Fiado"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    pedido = models.ForeignKey(
        "pedidos.Pedido", on_delete=models.PROTECT, related_name="pagamentos"
    )
    forma = models.CharField(max_length=10, choices=Forma.choices)
    valor = models.DecimalField(max_digits=10, decimal_places=2)
    troco = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="pagamentos",
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Pagamento"
        verbose_name_plural = "Pagamentos"

    def __str__(self) -> str:
        return f"{self.get_forma_display()} {self.valor}"
