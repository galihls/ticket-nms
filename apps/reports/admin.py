from django.contrib import admin

from .models import ReportExport


@admin.register(ReportExport)
class ReportExportAdmin(admin.ModelAdmin):
    list_display = ("file_name", "period", "date_from", "date_to", "created_by",
                    "created_at")
    list_filter = ("period",)
