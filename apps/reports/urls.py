from django.urls import path

from . import views

app_name = "reports"

urlpatterns = [
    path("", views.export_page, name="export"),
    path("unduh/", views.export_download, name="download"),
]
