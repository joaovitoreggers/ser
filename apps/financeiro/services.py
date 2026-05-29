from __future__ import annotations

from decimal import Decimal

from django.db.models import Sum

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
    pagamentos = pagamentos_do_turno(turno)
    por_forma: dict[str, Decimal] = {}
    for forma, _label in Pagamento.Forma.choices:
        total = pagamentos.filter(forma=forma).aggregate(s=Sum("valor"))["s"] or ZERO
        if total:
            por_forma[forma] = total

    total_pagamentos = pagamentos.aggregate(s=Sum("valor"))["s"] or ZERO
    dinheiro = por_forma.get(Pagamento.Forma.DINHEIRO, ZERO)

    movs = turno.movimentacoes.all()
    sangrias = (
        movs.filter(tipo=MovimentacaoCaixa.Tipo.SANGRIA).aggregate(s=Sum("valor"))["s"]
        or ZERO
    )
    suprimentos = (
        movs.filter(tipo=MovimentacaoCaixa.Tipo.SUPRIMENTO).aggregate(s=Sum("valor"))[
            "s"
        ]
        or ZERO
    )

    saldo_esperado = turno.valor_abertura + dinheiro + suprimentos - sangrias

    return {
        "por_forma": por_forma,
        "total_pagamentos": total_pagamentos,
        "dinheiro": dinheiro,
        "sangrias": sangrias,
        "suprimentos": suprimentos,
        "saldo_esperado": saldo_esperado,
        "num_pagamentos": pagamentos.count(),
    }
