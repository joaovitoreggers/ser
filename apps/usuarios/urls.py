from django.contrib.auth.views import LogoutView
from django.urls import path

from . import views

app_name = "usuarios"

urlpatterns = [
    path("login/", views.PerfilLoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("pin-login/", views.pin_login, name="pin_login"),
]
