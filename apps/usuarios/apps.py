from django.apps import AppConfig
from django.db.models.signals import post_migrate


def _sync_rbac_groups(sender, **kwargs):
    from .rbac import sync_groups

    sync_groups()


class UsuariosConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.usuarios"

    def ready(self) -> None:
        # Sem sender: roda a cada post_migrate. A última emissão (após todas as
        # Permissions de todos os apps existirem) fixa o estado correto, pois
        # create_permissions é por-app e a ordem de INSTALLED_APPS importa.
        post_migrate.connect(_sync_rbac_groups, dispatch_uid="sgr_sync_rbac_groups")
