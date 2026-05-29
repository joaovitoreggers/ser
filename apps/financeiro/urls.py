from django.urls import path

from . import views

app_name = "financeiro"

urlpatterns = [
    path("", views.CaixaTurnoView.as_view(), name="home"),
    path("turno/abrir/", views.TurnoAbrirView.as_view(), name="turno_abrir"),
    path("turno/fechar/", views.TurnoFecharView.as_view(), name="turno_fechar"),
    path("movimentacoes/nova/", views.MovimentacaoCreateView.as_view(), name="mov_nova"),
    path("turnos/", views.TurnoListView.as_view(), name="turno_list"),
    path("turnos/<uuid:pk>/", views.TurnoDetailView.as_view(), name="turno_detalhe"),
    path("recibo/<uuid:pk>/", views.ReciboView.as_view(), name="recibo"),
]
