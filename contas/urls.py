from django.urls import path

from . import views

app_name = "contas"

urlpatterns = [
    path("login", views.login_view, name="login"),
    path("sair", views.logout_view, name="logout"),
    path("apos-login", views.apos_login, name="apos_login"),
    path("esqueci-senha", views.esqueci_senha, name="esqueci_senha"),
    path("auth/confirm", views.confirmar_acesso, name="confirmar"),
    path("definir-senha", views.definir_senha, name="definir_senha"),
]
