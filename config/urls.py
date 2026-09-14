"""Peta URL utama Ticketing NMS."""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("", include(("apps.core.urls", "core"), namespace="core")),
    path("akun/", include(("apps.accounts.urls", "accounts"), namespace="accounts")),
    path("tiket/", include(("apps.tickets.urls", "tickets"), namespace="tickets")),
    path("solusi/", include(("apps.solutions.urls", "solutions"), namespace="solutions")),
    path("laporan/", include(("apps.reports.urls", "reports"), namespace="reports")),
    path("django-admin/", admin.site.urls),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

admin.site.site_header = f"{settings.APP_NAME} — Administrasi"
admin.site.site_title = settings.APP_NAME
admin.site.index_title = "Panel Administrasi"
