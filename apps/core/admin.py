from django.contrib import admin

from .models import ActivityLog, Notification


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "actor_label", "verb", "target_label", "subject")
    list_filter = ("verb",)
    search_fields = ("actor_label", "subject", "target_label")
    date_hierarchy = "created_at"


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("created_at", "title", "level", "is_read")
    list_filter = ("level", "is_read")
