from __future__ import annotations

from decimal import Decimal

from django.db.models import Avg, Count, F, Sum
from django.utils import timezone

from apps.cardapio.models import Prato
from apps.estoque.models import Ingrediente
from apps.financeiro.models import Pagamento
from apps.financeiro.services import get_turno_aberto, resumo_turno
from apps.pedidos.models import ItemPedido, Pedido

ZERO = Decimal("0.00")


def metricas_do_dia(restaurante) -> dict:
    """Indicadores financeiros e operacionais do dia para um restaurante.

    Reutilizado pela tela inicial (hub) e pelo dashboard gerencial.
    """
    hoje = timezone.localdate()
    rest = restaurante

    pagos_hoje = Pedido.objects.for_tenant(rest).filter(
        status=Pedido.Status.PAGO, fechado_em__date=hoje
    )
    agg = pagos_hoje.aggregate(
        faturamento=Sum("total"), num=Count("id"), ticket=Avg("total")
    )
    faturamento = agg["faturamento"] or ZERO
    num_pedidos = agg["num"] or 0
    ticket_medio = agg["ticket"] or ZERO

    pagamentos_hoje = Pagamento.objects.filter(
        pedido__restaurante=rest, criado_em__date=hoje
    )
    por_forma = [
        {"forma": row["forma"], "total": row["total"]}
        for row in pagamentos_hoje.values("forma")
        .annotate(total=Sum("valor"))
        .order_by("-total")
    ]

    turno = get_turno_aberto(rest)
    resumo = resumo_turno(turno) if turno else None

    pedidos_abertos = (
        Pedido.objects.for_tenant(rest)
        .filter(
            status__in=[
                Pedido.Status.ABERTO,
                Pedido.Status.EM_ATENDIMENTO,
                Pedido.Status.AGUARDANDO_PAGAMENTO,
            ]
        )
        .count()
    )
    itens_cozinha = ItemPedido.objects.filter(
        pedido__restaurante=rest,
        status__in=[ItemPedido.Status.EM_PREPARO, ItemPedido.Status.PRONTO],
    ).count()

    estoque_critico = (
        Ingrediente.objects.for_tenant(rest)
        .filter(estoque_atual__lte=F("estoque_minimo"))
        .count()
    )
    pratos_indisponiveis = (
        Prato.objects.for_tenant(rest).filter(disponivel=False).count()
    )

    return {
        "hoje": hoje,
        "faturamento": faturamento,
        "num_pedidos": num_pedidos,
        "ticket_medio": ticket_medio,
        "por_forma": por_forma,
        "turno": turno,
        "resumo": resumo,
        "pedidos_abertos": pedidos_abertos,
        "itens_cozinha": itens_cozinha,
        "estoque_critico": estoque_critico,
        "pratos_indisponiveis": pratos_indisponiveis,
    }
