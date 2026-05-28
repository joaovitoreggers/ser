from __future__ import annotations

from django.db import transaction
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
    e dispara alertas de estoque crítico / prato indisponível.

    A baixa roda sob lock de linha (select_for_update) com ingredientes travados
    em ordem determinística de id, serializando baixas concorrentes do KDS e
    evitando lost updates/deadlocks (§1 — alta carga)."""
    if not getattr(instance, "_tornou_pronto", False):
        return

    ficha = instance.prato.ficha
    restaurante_id = instance.prato.restaurante_id

    afetados = []
    with transaction.atomic():
        fis = list(ficha.ingredientes.filter(principal=True).order_by("ingrediente_id"))
        ing_ids = sorted({fi.ingrediente_id for fi in fis})
        from apps.estoque.models import Ingrediente as Ing

        travados = {
            i.id: i
            for i in Ing.objects.select_for_update().filter(id__in=ing_ids).order_by("id")
        }
        for fi in fis:
            ing = travados[fi.ingrediente_id]
            ing.estoque_atual -= fi.quantidade * instance.quantidade
            ing.save(update_fields=["estoque_atual"])
        afetados = list(travados.values())

    # alertas e indisponibilização após o commit (WS não deve ver estado não commitado)
    for ing in afetados:
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
