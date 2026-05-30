from django.contrib.auth.views import LogoutView
from django.urls import path

from . import views

app_name = "usuarios"

urlpatterns = [
    path("login/", views.PerfilLoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("pin/", views.PinPadView.as_view(), name="pin_pad"),
    path("pin-login/", views.pin_login, name="pin_login"),
    # Gestão de usuários (§5)
    path("usuarios/", views.UsuarioListView.as_view(), name="usuario_list"),
    path("usuarios/tabela/", views.UsuarioTabelaView.as_view(), name="usuario_tabela"),
    path("usuarios/novo/", views.UsuarioCreateView.as_view(), name="usuario_novo"),
    path("usuarios/<uuid:pk>/editar/", views.UsuarioUpdateView.as_view(), name="usuario_editar"),
    path("usuarios/<uuid:pk>/status/", views.UsuarioToggleAtivoView.as_view(), name="usuario_status"),
]
