from django.urls import path

from . import views

app_name = "solutions"

urlpatterns = [
    path("", views.solution_home, name="home"),
    path("jelajah/", views.browse, name="browse"),
    path("artikel/baru/", views.article_create, name="create"),
    path("<slug:slug>/", views.article_detail, name="detail"),
    path("<slug:slug>/ubah/", views.article_edit, name="edit"),
    path("<slug:slug>/nilai/", views.article_vote, name="vote"),
]
