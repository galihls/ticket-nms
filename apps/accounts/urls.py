from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("masuk/", views.LoginView.as_view(), name="login"),
    path("masuk/sso/", views.sso_login, name="sso_login"),
    path("keluar/", views.LogoutView.as_view(), name="logout"),
    path("profil/", views.profile, name="profile"),
    path("agent/", views.agent_list, name="agents"),
]
