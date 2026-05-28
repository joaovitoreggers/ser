from django.contrib import admin

from .models import MovimentacaoCaixa, Pagamento, TurnoCaixa


class MovimentacaoCaixaInline(admin.TabularInline):
    model = MovimentacaoCaixa
    extra = 0
    autocomplete_fields = ("usuario", "autorizado_por")


@admin.register(TurnoCaixa)
class TurnoCaixaAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "restaurante",
        "usuario",
        "valor_abertura",
        "valor_fechamento",
        "status",
        "aberto_em",
    )
    list_filter = ("restaurante", "status")
    autocomplete_fields = ("restaurante", "usuario")
    inlines = (MovimentacaoCaixaInline,)


@admin.register(Pagamento)
class PagamentoAdmin(admin.ModelAdmin):
    list_display = ("id", "pedido", "forma", "valor", "troco", "usuario", "criado_em")
    list_filter = ("forma",)
    autocomplete_fields = ("pedido", "usuario")
