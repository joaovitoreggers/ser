from __future__ import annotations

from django.db.models.signals import pre_save
from django.dispatch import receiver

from .models import HistoricoPreco, Prato


@receiver(pre_save, sender=Prato)
def prato_historico_preco(sender, instance: Prato, **kwargs):
    """§3D — registra HistoricoPreco quando preco_venda muda em relação ao banco.
    O usuário responsável deve ser anexado em instance._usuario_alteracao pela view."""
    if instance._state.adding or not instance.pk:
        return

    anterior = (
        Prato.objects.filter(pk=instance.pk)
        .values_list("preco_venda", flat=True)
        .first()
    )
    if anterior is None or anterior == instance.preco_venda:
        return

    HistoricoPreco.objects.create(
        prato=instance,
        preco_anterior=anterior,
        preco_novo=instance.preco_venda,
        usuario=getattr(instance, "_usuario_alteracao", None),
    )
