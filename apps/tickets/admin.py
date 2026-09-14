from django.contrib import admin

from .models import Ticket, TicketReply


class TicketReplyInline(admin.TabularInline):
    model = TicketReply
    extra = 0


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ("number", "subject", "ticket_type", "status", "priority",
                    "assignee", "opened_at")
    list_filter = ("status", "ticket_type", "priority", "group")
    search_fields = ("number", "subject", "requester_name", "site_code")
    date_hierarchy = "opened_at"
    inlines = [TicketReplyInline]
