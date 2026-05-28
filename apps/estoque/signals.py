from __future__ import annotations

from decimal import Decimal

from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import EntradaEstoque, Ingrediente


@receiver(post_save, sender=EntradaEstoque)
def entrada_estoque_cmp(sender, instance: EntradaEstoque, created: bool, **kwargs):
    """§3A — Recebimento de insumo: atualiza estoque e Custo Médio Ponderado (CMP),
    depois dispara a cascata de recálculo de custos (§3B nível 1).

    Lê/escreve sob lock de linha (select_for_update) para serializar entradas
    concorrentes do mesmo ingrediente e evitar lost updates (§1 — alta carga)."""
    if not created:
        return

    with transaction.atomic():
        ing = Ingrediente.objects.select_for_update().get(pk=instance.ingrediente_id)
        estoque_atual = ing.estoque_atual
        custo_atual = ing.custo_unitario
        q = instance.quantidade
        c = instance.custo_unitario

        novo_estoque = estoque_atual + q
        if novo_estoque > 0:
            novo_custo = ((estoque_atual * custo_atual) + (q * c)) / novo_estoque
            ing.custo_unitario = novo_custo.quantize(Decimal("0.0001"))
        ing.estoque_atual = novo_estoque
        ing.save(update_fields=["estoque_atual", "custo_unitario"])

    _cascata_recalcular_fichas(ing)


def _cascata_recalcular_fichas(ingrediente: Ingrediente) -> None:
    """Cascata nível 1: recalcula toda FichaTecnica que usa o ingrediente como
    principal. Cada save dispara o post_save da ficha → atualização do Prato."""
    from apps.fichas.models import FichaTecnica

    fichas = FichaTecnica.objects.filter(
        ingredientes__ingrediente=ingrediente,
        ingredientes__principal=True,
    ).distinct()
    for ficha in fichas:
        ficha.recalcular_custo()
