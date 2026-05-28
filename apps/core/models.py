from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models


class TenantQuerySet(models.QuerySet):
    """QuerySet that knows how to scope rows to a single tenant (Restaurante)."""

    def for_tenant(self, restaurante) -> "TenantQuerySet":
        return self.filter(restaurante=restaurante)


class TenantManager(models.Manager.from_queryset(TenantQuerySet)):
    """Default manager exposing `for_tenant(restaurante)` to enforce multi-tenancy.

    Never call `.all()` without scoping in operational code — always go through
    `for_tenant()` so a tenant can only ever see its own rows.
    """


class UUIDModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True


class TenantModel(UUIDModel):
    """Abstract base for every tenant-scoped operational table."""

    restaurante = models.ForeignKey(
        "core.Restaurante",
        on_delete=models.CASCADE,
        related_name="%(class)ss",
    )

    objects = TenantManager()

    class Meta:
        abstract = True


class Restaurante(UUIDModel):
    nome = models.CharField(max_length=200)
    cnpj = models.CharField(max_length=18, unique=True)
    margem_padrao = models.DecimalField(max_digits=5, decimal_places=2, default=60)
    permitir_estoque_negativo = models.BooleanField(default=True)
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Restaurante"
        verbose_name_plural = "Restaurantes"

    def __str__(self) -> str:
        return self.nome


class LogAuditoria(UUIDModel):
    restaurante = models.ForeignKey(
        Restaurante, on_delete=models.CASCADE, related_name="logs"
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="logs_auditoria",
    )
    acao = models.CharField(max_length=100)
    entidade = models.CharField(max_length=100)
    entidade_id = models.UUIDField(null=True, blank=True)
    dados_antes = models.JSONField(default=dict, blank=True)
    dados_depois = models.JSONField(default=dict, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    objects = TenantManager()

    class Meta:
        verbose_name = "Log de Auditoria"
        verbose_name_plural = "Logs de Auditoria"
        indexes = [
            models.Index(
                fields=["entidade", "entidade_id", "-criado_em"],
                name="idx_log_entidade",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.acao} {self.entidade} @ {self.criado_em:%Y-%m-%d %H:%M}"
