from __future__ import annotations

import uuid

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.db import models

from apps.core.models import TenantManager


class PerfilUsuario(models.Model):
    class Perfil(models.TextChoices):
        ADMIN = "admin", "Administrador"
        GERENTE = "gerente", "Gerente"
        GARCOM = "garcom", "Garçom"
        COZINHEIRO = "cozinheiro", "Cozinheiro"
        CAIXA = "caixa", "Caixa"
        ALMOXARIFE = "almoxarife", "Almoxarife"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="perfil"
    )
    restaurante = models.ForeignKey(
        "core.Restaurante", on_delete=models.CASCADE, related_name="perfis"
    )
    perfil = models.CharField(max_length=20, choices=Perfil.choices)
    pin_hash = models.CharField(max_length=128, blank=True)

    objects = TenantManager()

    class Meta:
        verbose_name = "Perfil de Usuário"
        verbose_name_plural = "Perfis de Usuário"

    def set_pin(self, raw_pin: str) -> None:
        self.pin_hash = make_password(raw_pin)

    def check_pin(self, raw_pin: str) -> bool:
        return bool(self.pin_hash) and check_password(raw_pin, self.pin_hash)

    def __str__(self) -> str:
        return f"{self.user} ({self.get_perfil_display()})"
