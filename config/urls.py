from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("apps.usuarios.urls")),
    path("relatorios/", include("apps.relatorios.urls")),
    path("pedidos/", include("apps.pedidos.urls")),
    path("estoque/", include("apps.estoque.urls")),
    path("fichas/", include("apps.fichas.urls")),
]
