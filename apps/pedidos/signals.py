from __future__ import annotations

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone

from apps.core.realtime import notify

from .models import ItemPedido


@receiver(pre_save, sender=ItemPedido)
def itempedido_detecta_pronto(sender, instance: ItemPedido, **kwargs):
    """Marca a transição para 'pronto' (idempotência da baixa de estoque)."""
    instance._tornou_pronto = False
    if instance.status != ItemPedido.Status.PRONTO:
        return

    if instance._state.adding or not instance.pk:
        instance._tornou_pronto = True
    else:
        status_antigo = (
            ItemPedido.objects.filter(pk=instance.pk)
            .values_list("status", flat=True)
            .first()
        )
        instance._tornou_pronto = status_antigo != ItemPedido.Status.PRONTO

    if instance._tornou_pronto and instance.pronto_em is None:
        instance.pronto_em = timezone.now()


@receiver(post_save, sender=ItemPedido)
def itempedido_baixa_estoque(sender, instance: ItemPedido, **kwargs):
    """§3C — ao ficar 'pronto', baixa o estoque dos ingredientes principais da ficha
    e dispara alertas de estoque crítico / prato indisponível."""
    if not getattr(instance, "_tornou_pronto", False):
        return

    ficha = instance.prato.ficha
    restaurante_id = instance.prato.restaurante_id
    itens_ficha = ficha.ingredientes.filter(principal=True).select_related(
        "ingrediente"
    )

    for fi in itens_ficha:
        ing = fi.ingrediente
        ing.estoque_atual -= fi.quantidade * instance.quantidade
        ing.save(update_fields=["estoque_atual"])

        if ing.estoque_atual <= ing.estoque_minimo:
            notify(
                restaurante_id,
                "estoque_alerta",
                {
                    "ingrediente_id": str(ing.id),
                    "ingrediente": ing.nome,
                    "estoque_atual": str(ing.estoque_atual),
                    "estoque_minimo": str(ing.estoque_minimo),
                },
            )

        if ing.estoque_atual <= 0:
            _indisponibilizar_pratos(ing, restaurante_id)


def _indisponibilizar_pratos(ingrediente, restaurante_id) -> None:
    from apps.cardapio.models import Prato

    pratos = (
        Prato.objects.filter(
            ficha__ingredientes__ingrediente=ingrediente,
            ficha__ingredientes__principal=True,
            disponivel=True,
        )
        .distinct()
    )
    for prato in pratos:
        prato.disponivel = False
        prato.motivo_indisponivel = f"Sem estoque de {ingrediente.nome}."
        prato.save(update_fields=["disponivel", "motivo_indisponivel"])
        notify(
            restaurante_id,
            "prato_indisponivel",
            {"prato_id": str(prato.id), "prato": prato.nome},
        )
