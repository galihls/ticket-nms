from django.contrib import admin

from .models import Article

@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "status", "author", "views", "updated_at")
    list_filter = ("status", "category")
    search_fields = ("title", "body", "tags")
    prepopulated_fields = {"slug": ("title",)}
