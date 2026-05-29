from __future__ import annotations

from django.urls import path

from . import views

app_name = "fichas"

urlpatterns = [
    path("", views.FichaTecnicaListView.as_view(), name="ficha_list"),
    path("nova/", views.FichaTecnicaCreateView.as_view(), name="ficha_nova"),
    path(
        "<uuid:pk>/editar/",
        views.FichaTecnicaUpdateView.as_view(),
        name="ficha_editar",
    ),
    path(
        "<uuid:pk>/excluir/",
        views.FichaTecnicaDeleteView.as_view(),
        name="ficha_excluir",
    ),
]
