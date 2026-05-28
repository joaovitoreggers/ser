from django.urls import path

from apps.core.views import StubPageView

app_name = "estoque"

urlpatterns = [
    path(
        "",
        StubPageView.as_view(
            page_name="Estoque", perfis_permitidos=("almoxarife", "gerente", "admin")
        ),
        name="index",
    ),
]
