from django.urls import path

from . import views

app_name = "tickets"

urlpatterns = [
    path("", views.ticket_list, name="list"),
    path("baru/", views.ticket_create, name="create"),
    path("aksi-massal/", views.ticket_bulk, name="bulk"),
    path("companies/", views.company_list, name="company_list"),
    path("companies/<int:pk>/edit/", views.company_edit, name="company_edit"),
    path("companies/<int:pk>/toggle/", views.company_toggle, name="company_toggle"),
    path("companies/<int:pk>/delete/", views.company_delete, name="company_delete"),
    path("<str:number>/", views.ticket_detail, name="detail"),
    path("<str:number>/ubah/", views.ticket_edit, name="edit"),
    path("<str:number>/balas/", views.ticket_reply, name="reply"),
    path("<str:number>/properti/", views.ticket_update_properties, name="properties"),
    path("<str:number>/tutup/", views.ticket_close, name="close"),
    path("<str:number>/buka-ulang/", views.ticket_reopen, name="reopen"),
    path("<str:number>/hapus/", views.ticket_delete, name="delete"),
]
