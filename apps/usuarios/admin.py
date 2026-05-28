from django.contrib import admin

from .models import PerfilUsuario


@admin.register(PerfilUsuario)
class PerfilUsuarioAdmin(admin.ModelAdmin):
    list_display = ("user", "restaurante", "perfil")
    list_filter = ("perfil", "restaurante")
    search_fields = ("user__username", "user__email")
    autocomplete_fields = ("user", "restaurante")
    exclude = ("pin_hash",)
