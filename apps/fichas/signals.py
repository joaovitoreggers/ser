from __future__ import annotations

from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.core.realtime import notify

from .models import FichaTecnica


@receiver(post_save, sender=FichaTecnica)
def ficha_atualiza_prato(sender, instance: FichaTecnica, **kwargs):
    """§3B nível 2 — o post_save da ficha dispara Prato.atualizar_custo().
    Se a margem ficar abaixo da margem_padrao do restaurante, emite margem_alerta."""
    prato = getattr(instance, "prato", None)
    if prato is None:
        return

    prato.atualizar_custo()

    margem_padrao = instance.restaurante.margem_padrao
    if prato.margem_lucro < margem_padrao:
        notify(
            instance.restaurante_id,
            "margem_alerta",
            {
                "prato_id": str(prato.id),
                "prato": prato.nome,
                "margem_lucro": str(prato.margem_lucro),
                "margem_padrao": str(margem_padrao),
            },
        )
