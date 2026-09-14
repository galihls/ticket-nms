from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("aktivitas/", views.activity_log, name="activity_log"),
    path("notifikasi/", views.notifications, name="notifications"),
    path("notifikasi/tandai-dibaca/", views.notifications_read, name="notifications_read"),
    path("pencarian/", views.search, name="search"),
    path("panduan-komponen/", views.styleguide, name="styleguide"),
    path("akses-ditolak/", views.forbidden, name="forbidden"),
    path("healthz/", views.healthz, name="healthz"),
]
