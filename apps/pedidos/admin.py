from django.contrib import admin

from .models import ItemPedido, Mesa, Pedido


@admin.register(Mesa)
class MesaAdmin(admin.ModelAdmin):
    list_display = ("numero", "restaurante", "status")
    list_filter = ("restaurante", "status")
    search_fields = ("numero",)


class ItemPedidoInline(admin.TabularInline):
    model = ItemPedido
    extra = 0
    autocomplete_fields = ("prato",)
    readonly_fields = ("preco_unitario", "custo_unitario", "subtotal")


@admin.register(Pedido)
class PedidoAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "restaurante",
        "mesa",
        "tipo",
        "status",
        "subtotal",
        "desconto",
        "total",
        "criado_em",
    )
    list_filter = ("restaurante", "status", "tipo")
    search_fields = ("id",)
    autocomplete_fields = ("restaurante", "mesa", "usuario")
    readonly_fields = ("subtotal", "total", "criado_em")
    inlines = (ItemPedidoInline,)
