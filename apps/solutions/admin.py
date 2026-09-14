from django.contrib import admin

from .models import Article, Folder


@admin.register(Folder)
class FolderAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "order")
    list_filter = ("category",)
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = ("title", "folder", "status", "author", "views", "updated_at")
    list_filter = ("status", "folder__category", "folder")
    search_fields = ("title", "body", "tags")
    prepopulated_fields = {"slug": ("title",)}
