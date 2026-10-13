from django.contrib import admin

from .models import Ticket, TicketReply, Company


class TicketReplyInline(admin.TabularInline):
    model = TicketReply
    extra = 0


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "contact_person", "contact_phone", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name", "code", "contact_person", "contact_phone")


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ("number", "subject", "ticket_type", "status", "priority",
                    "company", "assignee", "opened_at")
    list_filter = ("status", "ticket_type", "priority", "company")
    search_fields = ("number", "subject", "requester_name", "site_code", "company")
    date_hierarchy = "opened_at"
    inlines = [TicketReplyInline]
