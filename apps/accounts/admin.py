from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("username", "display_name", "email", "department",
                    "shift", "is_active", "is_staff")
    list_filter = ("is_active", "is_staff", "is_superuser", "shift", "department")
    search_fields = ("username", "first_name", "last_name", "email", "nik")

    fieldsets = BaseUserAdmin.fieldsets + (
        ("Data Kepegawaian", {
            "fields": ("nik", "phone", "department", "position", "shift"),
        }),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ("Data Kepegawaian", {
            "fields": ("first_name", "last_name", "email", "nik",
                       "phone", "department", "position", "shift"),
        }),
    )

    @admin.display(description="nama")
    def display_name(self, obj):
        return obj.display_name
