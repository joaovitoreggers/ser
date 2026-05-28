from django.urls import path

from apps.core.views import StubPageView

app_name = "pedidos"

urlpatterns = [
    path(
        "mesas/",
        StubPageView.as_view(
            page_name="Mesas", perfis_permitidos=("garcom", "gerente", "admin")
        ),
        name="mesas",
    ),
    path(
        "kds/",
        StubPageView.as_view(
            page_name="KDS", perfis_permitidos=("cozinheiro", "gerente", "admin")
        ),
        name="kds",
    ),
    path(
        "caixa/",
        StubPageView.as_view(
            page_name="Caixa", perfis_permitidos=("caixa", "gerente", "admin")
        ),
        name="caixa",
    ),
]
