from django.urls import path

from apps.core.views import StubPageView

app_name = "relatorios"

urlpatterns = [
    path(
        "dashboard/",
        StubPageView.as_view(
            page_name="Dashboard", perfis_permitidos=("admin", "gerente")
        ),
        name="dashboard",
    ),
]
