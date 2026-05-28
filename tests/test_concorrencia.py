from __future__ import annotations

import threading
from datetime import date
from decimal import Decimal

import pytest
from django.db import connection

from apps.core.models import Restaurante
from apps.estoque.models import EntradaEstoque, Ingrediente, UnidadeMedida


@pytest.mark.django_db(transaction=True)
def test_entradas_concorrentes_somam_corretamente():
    """Smoke test de execução concorrente do signal de CMP.

    Roda várias EntradaEstoque em paralelo (conexões separadas) e verifica que
    nenhuma levanta exceção e que o estoque final bate com a soma.

    NOTA: este teste NÃO reproduz de forma determinística o lost update que o
    select_for_update no signal previne — o GIL + Postgres local serializam o
    read-modify-write na prática. A correção se justifica por correção-de-design
    (lock de linha serializa escritores), não por este teste. Mantido como
    detector de regressões grosseiras (deadlock, erro sob concorrência)."""
    r = Restaurante.objects.create(nome="Concorrência", cnpj="33.333.333/0001-33")
    ing = Ingrediente.objects.create(
        restaurante=r, nome="Insumo", unidade_medida=UnidadeMedida.GRAMA
    )

    n_threads = 8
    barreira = threading.Barrier(n_threads)
    erros: list[Exception] = []

    def worker():
        try:
            barreira.wait()  # libera todas as threads juntas
            EntradaEstoque.objects.create(
                restaurante=r,
                ingrediente=ing,
                quantidade=Decimal("100"),
                custo_unitario=Decimal("0.0200"),
                data_entrada=date.today(),
            )
        except Exception as exc:  # pragma: no cover - só registra p/ asserção
            erros.append(exc)
        finally:
            connection.close()

    threads = [threading.Thread(target=worker) for _ in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not erros, erros
    ing.refresh_from_db()
    assert ing.estoque_atual == Decimal("100") * n_threads
