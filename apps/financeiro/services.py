from __future__ import annotations

from decimal import Decimal

from django.db.models import Count, Sum

from .models import MovimentacaoCaixa, Pagamento, TurnoCaixa

ZERO = Decimal("0.00")


def get_turno_aberto(restaurante) -> TurnoCaixa | None:
    """Retorna o turno de caixa aberto do restaurante (no máximo um), ou None."""
    return (
        TurnoCaixa.objects.for_tenant(restaurante)
        .filter(status=TurnoCaixa.Status.ABERTO)
        .order_by("-aberto_em")
        .first()
    )


def pagamentos_do_turno(turno: TurnoCaixa):
    """Pagamentos do tenant na janela temporal do turno.

    O modelo ``Pagamento`` (conforme especificação) não possui FK para o turno,
    então a associação é feita pela janela [aberto_em, fechado_em] do turno."""
    qs = Pagamento.objects.filter(
        pedido__restaurante=turno.restaurante,
        criado_em__gte=turno.aberto_em,
    )
    if turno.fechado_em:
        qs = qs.filter(criado_em__lte=turno.fechado_em)
    return qs


def resumo_turno(turno: TurnoCaixa) -> dict:
    """Consolida pagamentos e movimentações do turno e o saldo de caixa esperado.

    Saldo esperado (gaveta) = abertura + dinheiro recebido + suprimentos − sangrias.
    Formas eletrônicas (débito/crédito/pix/voucher/fiado) não alteram a gaveta."""
    # Uma única query agrupada por forma (em vez de uma por forma + totais
    # separados): evita N+1 quando chamado em loop (ex.: histórico de turnos).
    por_forma: dict[str, Decimal] = {}
    total_pagamentos = ZERO
    num_pagamentos = 0
    for row in (
        pagamentos_do_turno(turno)
        .values("forma")
        .annotate(total=Sum("valor"), n=Count("id"))
    ):
        total = row["total"] or ZERO
        if total:
            por_forma[row["forma"]] = total
        total_pagamentos += total
        num_pagamentos += row["n"]

    dinheiro = por_forma.get(Pagamento.Forma.DINHEIRO, ZERO)

    # Uma única query agrupada por tipo de movimentação.
    movs_por_tipo = {
        row["tipo"]: (row["total"] or ZERO)
        for row in turno.movimentacoes.values("tipo").annotate(total=Sum("valor"))
    }
    sangrias = movs_por_tipo.get(MovimentacaoCaixa.Tipo.SANGRIA, ZERO)
    suprimentos = movs_por_tipo.get(MovimentacaoCaixa.Tipo.SUPRIMENTO, ZERO)

    saldo_esperado = turno.valor_abertura + dinheiro + suprimentos - sangrias

    return {
        "por_forma": por_forma,
        "total_pagamentos": total_pagamentos,
        "dinheiro": dinheiro,
        "sangrias": sangrias,
        "suprimentos": suprimentos,
        "saldo_esperado": saldo_esperado,
        "num_pagamentos": num_pagamentos,
    }
