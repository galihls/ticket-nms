from django.contrib import admin

from .models import Ticket, TicketReply, Company, CompanyService


class CompanyServiceInline(admin.TabularInline):
    model = CompanyService
    extra = 1
    fields = ("service_id", "service_name", "device_solution", "brand", "is_active")


class TicketReplyInline(admin.TabularInline):
    model = TicketReply
    extra = 0


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ("name", "customer_id", "code", "partner", "contact_person", "contact_phone", "service_count", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name", "code", "customer_id", "partner", "contact_person", "contact_phone")
    inlines = [CompanyServiceInline]


@admin.register(CompanyService)
class CompanyServiceAdmin(admin.ModelAdmin):
    list_display = ("service_id", "service_name", "company", "device_solution", "brand", "is_active")
    list_filter = ("is_active", "company", "brand")
    search_fields = ("service_id", "service_name", "device_solution", "brand", "company__name")


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ("number", "subject", "ticket_type", "status", "priority",
                    "company", "customer_id", "service_id", "assignee", "opened_at")
    list_filter = ("status", "ticket_type", "priority", "company")
    search_fields = ("number", "subject", "requester_name", "site_code", "company", "customer_id", "service_id")
    date_hierarchy = "opened_at"
    inlines = [TicketReplyInline]
