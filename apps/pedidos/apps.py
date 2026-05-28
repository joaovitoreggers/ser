from django.apps import AppConfig


class PedidosConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.pedidos"

    def ready(self) -> None:
        from . import signals  # noqa: F401
