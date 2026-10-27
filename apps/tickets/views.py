import json
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import models
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.accounts.models import User
from apps.core import periods
from apps.core.models import ActivityLog, Notification

from .forms import GROUPS, CloseTicketForm, ReplyForm, TicketForm, CompanyForm, CompanyServiceForm
from .models import Ticket, TicketReply, Company, CompanyService

SORTS = [
    ("-opened_at", "Newest created"),
    ("opened_at", "Oldest created"),
    ("-updated_at", "Recently updated"),
    ("priority", "Level"),
    ("number", "Ticket number"),
]


def _locked(request, ticket):
    """True (and show message) if user is no longer allowed to edit this ticket."""
    if ticket.can_edit(request.user):
        return False
    messages.error(
        request,
        f"Ticket {ticket.number} has been closed for more than "
        f"{int(Ticket.CLOSED_EDIT_WINDOW.total_seconds() // 60)} minutes. "
        "Only administrators can edit it.",
    )
    return True


@login_required
def ticket_list(request):
    qs = Ticket.objects.select_related("assignee")

    status = request.GET.getlist("status")
    ticket_type = request.GET.getlist("type")
    priority = request.GET.getlist("priority")
    high_priority = request.GET.get("high_priority", "")
    assignee = request.GET.get("assignee", "")
    group = request.GET.get("group", "")
    q = request.GET.get("q", "").strip()
    sort = request.GET.get("sort", "-opened_at")

    if high_priority == "1":
        qs = qs.high_priority()
    if status:
        qs = qs.filter(status__in=status)
    if ticket_type:
        qs = qs.filter(ticket_type__in=ticket_type)
    if priority:
        qs = qs.filter(priority__in=priority)
    if assignee == "none":
        qs = qs.filter(assignee__isnull=True)
    elif assignee == "me":
        qs = qs.filter(assignee=request.user)
    elif assignee:
        qs = qs.filter(assignee_id=assignee)
    if group:
        qs = qs.filter(group=group)
    if q:
        qs = qs.filter(Q(number__icontains=q) | Q(subject__icontains=q)
                       | Q(requester_name__icontains=q) | Q(site_code__icontains=q))

    # Filter rentang tanggal hanya dipakai kalau memang diminta, supaya daftar
    # tiket tidak diam-diam menyembunyikan tiket lama.
    date_range = None
    if request.GET.get("preset") or request.GET.get("from") or request.GET.get("to"):
        date_range = periods.resolve(request)
        qs = qs.in_range(date_range.start, date_range.end)

    if sort not in dict(SORTS):
        sort = "-opened_at"
    if sort == "priority":
        # Urutan prioritas mengikuti tingkat kegentingan, bukan abjad
        order = {"high": 1, "medium": 2, "low": 3}
        qs = sorted(qs, key=lambda t: (order.get(t.priority, 9), -t.id))
    else:
        qs = qs.order_by(sort)

    page = Paginator(qs, 15).get_page(request.GET.get("page"))

    facets = Ticket.objects.aggregate(
        all=Count("id"),
        open=Count("id", filter=Q(status=Ticket.Status.OPEN)),
        outstanding=Count("id", filter=Q(status=Ticket.Status.OUTSTANDING)),
        closed=Count("id", filter=Q(status=Ticket.Status.CLOSED)),
        mine=Count("id", filter=Q(assignee=request.user)),
        unassigned=Count("id", filter=Q(assignee__isnull=True)),
    )
    facets["high_priority"] = Ticket.objects.high_priority().count()

    return render(request, "tickets/list.html", {
        "page_title": "Tickets",
        "breadcrumb": [("Tickets", None)],
        "page_obj": page,
        "facets": facets,
        "statuses": Ticket.Status.choices,
        "types": Ticket.Type.choices,
        "priorities": Ticket.Priority.choices,
        "groups": GROUPS,
        "agents": User.objects.filter(is_active=True),
        "sorts": SORTS,
        "selected": {
            "status": status, "type": ticket_type, "priority": priority,
            "high_priority": high_priority,
            "assignee": assignee, "group": group, "sort": sort, "q": q,
        },
        "range": date_range,
        "presets": periods.PRESETS,
        "has_filter": any([status, ticket_type, priority, high_priority, assignee, group, q, date_range]),
        "querystring": _querystring(request, drop=["page"]),
    })


def _querystring(request, drop=()):
    params = request.GET.copy()
    for key in drop:
        params.pop(key, None)
    encoded = params.urlencode()
    return f"&{encoded}" if encoded else ""


@login_required
def ticket_detail(request, number):
    ticket = get_object_or_404(
        Ticket.objects.select_related("assignee", "created_by"), number=number)

    return render(request, "tickets/detail.html", {
        "page_title": ticket.number,
        "breadcrumb": [("Tickets", reverse("tickets:list")), (ticket.number, None)],
        "ticket": ticket,
        "can_edit": ticket.can_edit(request.user),
        "replies": ticket.replies.select_related("author"),
        "reply_form": ReplyForm(),
        "close_form": CloseTicketForm(initial={
            "problem_category": ticket.problem_category,
            "problem_detail": ticket.problem_detail,
        }),
        "statuses": Ticket.Status.choices,
        "priorities": Ticket.Priority.choices,
        "types": Ticket.Type.choices,
        "problem_categories": Ticket.ProblemCategory.choices,
        "groups": GROUPS,
        "agents": User.objects.filter(is_active=True),
        "history": ActivityLog.objects.filter(target_label=ticket.number)[:20],
        "related": Ticket.objects.filter(site_code=ticket.site_code)
                                .exclude(pk=ticket.pk)[:4] if ticket.site_code else [],
    })


def _get_companies_data_json():
    """Serialize active companies and their services for dynamic form population."""
    data = {}
    for c in Company.objects.filter(is_active=True).prefetch_related("services").order_by("name"):
        data[c.name] = {
            "id": c.id,
            "name": c.name,
            "customer_id": c.customer_id,
            "partner": c.partner,
            "services": [
                {
                    "id": s.id,
                    "service_id": s.service_id,
                    "service_name": s.service_name,
                    "device_solution": s.device_solution,
                    "brand": s.brand,
                }
                for s in c.services.filter(is_active=True)
            ]
        }
    return json.dumps(data)


@login_required
def ticket_create(request):
    form = TicketForm(request.POST or None)

    # Pratinjau nomor supaya agent tahu format penomoran sebelum menyimpan
    preview_type = request.POST.get("ticket_type") or request.GET.get("type") or Ticket.Type.PROBLEM
    if preview_type not in dict(Ticket.Type.choices):
        preview_type = Ticket.Type.PROBLEM

    if request.method == "POST" and form.is_valid():
        ticket = form.save(commit=False)
        ticket.created_by = request.user
        ticket.requester_name = request.user.display_name
        ticket.requester_email = request.user.email
        ticket.save()

        ActivityLog.record(
            request.user, ActivityLog.Verb.TICKET_CREATE,
            target_label=ticket.number, subject=ticket.subject,
            status=ticket.get_status_display(),
            pic=ticket.requester_phone if ticket.requester_phone else "No PIC number",
            url=ticket.get_absolute_url(),
        )
        Notification.objects.create(
            title=f"New ticket {ticket.number}",
            body=f"{ticket.subject} · {ticket.get_priority_display()}",
            url=ticket.get_absolute_url(), actor=request.user,
            level=(Notification.Level.DANGER
                   if ticket.priority == Ticket.Priority.HIGH
                   else Notification.Level.INFO),
        )
        messages.success(request, f"Ticket {ticket.number} created successfully.")
        return redirect(ticket)

    if request.method == "POST":
        messages.error(request, "Please check the highlighted required fields.")

    preview_numbers = {t: Ticket.next_number(t) for t, _ in Ticket.Type.choices}

    return render(request, "tickets/form.html", {
        "page_title": "Create New Ticket",
        "breadcrumb": [("Tickets", reverse("tickets:list")), ("Create Ticket", None)],
        "form": form,
        "number_preview": preview_numbers.get(preview_type, Ticket.next_number(preview_type)),
        "preview_numbers": preview_numbers,
        "preview_type": preview_type,
        "companies_data_json": _get_companies_data_json(),
        "is_edit": False,
    })


@login_required
def ticket_edit(request, number):
    ticket = get_object_or_404(Ticket, number=number)
    if _locked(request, ticket):
        return redirect(ticket)
    form = TicketForm(request.POST or None, instance=ticket)

    if request.method == "POST" and form.is_valid():
        form.save()
        ActivityLog.record(
            request.user, ActivityLog.Verb.TICKET_UPDATE,
            target_label=ticket.number, subject=ticket.subject,
            status=ticket.get_status_display(),
            pic=ticket.requester_phone if ticket.requester_phone else "No PIC number",
            url=ticket.get_absolute_url(),
        )
        messages.success(request, f"Ticket {ticket.number} changes saved.")
        return redirect(ticket)

    return render(request, "tickets/form.html", {
        "page_title": f"Edit {ticket.number}",
        "breadcrumb": [("Tickets", reverse("tickets:list")),
                       (ticket.number, ticket.get_absolute_url()), ("Edit", None)],
        "form": form,
        "ticket": ticket,
        "number_preview": ticket.number,
        "preview_type": ticket.ticket_type,
        "companies_data_json": _get_companies_data_json(),
        "is_edit": True,
    })


@login_required
@require_POST
def ticket_reply(request, number):
    ticket = get_object_or_404(Ticket, number=number)
    if _locked(request, ticket):
        return redirect(ticket)
    form = ReplyForm(request.POST)

    if form.is_valid():
        reply = form.save(commit=False)
        reply.ticket = ticket
        reply.author = request.user
        reply.author_label = request.user.display_name
        reply.save()

        # Catatan tidak lagi mengubah status. Open → Outstanding kini otomatis
        # berdasarkan waktu (lihat Ticket.AUTO_OUTSTANDING_AFTER).
        if not ticket.first_response_at:
            ticket.first_response_at = timezone.now()
            ticket.save(update_fields=["first_response_at", "updated_at"])
        else:
            ticket.save(update_fields=["updated_at"])

        verb = (ActivityLog.Verb.TICKET_NOTE if reply.is_private
                else ActivityLog.Verb.TICKET_REPLY)
        ActivityLog.record(
            request.user, verb, target_label=ticket.number, subject=ticket.subject,
            status=ticket.get_status_display(),
            pic=ticket.requester_phone if ticket.requester_phone else "No PIC number",
            reason=reply.body[:200], url=ticket.get_absolute_url(),
        )
        messages.success(request, "Internal note added." if reply.is_private
                         else "Reply sent.")
    else:
        messages.error(request, "Reply cannot be empty.")

    return redirect(ticket)


@login_required
@require_POST
def ticket_update_properties(request, number):
    """Properties panel in detail page — update status, priority, PIC, group."""
    ticket = get_object_or_404(Ticket, number=number)
    if _locked(request, ticket):
        return redirect(ticket)
    changes = []

    field_map = {
        "status": (Ticket.Status, "Status"),
        "priority": (Ticket.Priority, "Level"),
        "ticket_type": (Ticket.Type, "Type"),
    }
    for field, (choices, label) in field_map.items():
        value = request.POST.get(field)
        if value and value in dict(choices.choices) and value != getattr(ticket, field):
            old = getattr(ticket, f"get_{field}_display")()
            setattr(ticket, field, value)
            changes.append(f"{label}: {old} → {getattr(ticket, f'get_{field}_display')()}")

    if ticket.ticket_type == Ticket.Type.FEATURE and ticket.priority == Ticket.Priority.LOW:
        ticket.priority = Ticket.Priority.MEDIUM
    elif ticket.ticket_type == Ticket.Type.RELOCATION and ticket.priority != Ticket.Priority.MEDIUM:
        ticket.priority = Ticket.Priority.MEDIUM

    assignee_id = request.POST.get("assignee")
    if assignee_id is not None:
        new_assignee = (User.objects.filter(pk=assignee_id).first()
                        if assignee_id else None)
        if new_assignee != ticket.assignee:
            old = ticket.assignee.display_name if ticket.assignee else "Unassigned"
            ticket.assignee = new_assignee
            new = new_assignee.display_name if new_assignee else "Unassigned"
            changes.append(f"PIC: {old} → {new}")

    group = request.POST.get("group")
    if group is not None and group != ticket.group:
        changes.append(f"Group: {ticket.group or '—'} → {group or '—'}")
        ticket.group = group

    if ticket.ticket_type == Ticket.Type.PROBLEM:
        prob_cat = request.POST.get("problem_category")
        if prob_cat is not None and prob_cat != ticket.problem_category:
            old_c = ticket.get_problem_category_display() or "None"
            ticket.problem_category = prob_cat
            new_c = ticket.get_problem_category_display() or "None"
            changes.append(f"Category: {old_c} → {new_c}")
        prob_det = request.POST.get("problem_detail")
        if prob_det is not None and prob_det.strip() != ticket.problem_detail:
            ticket.problem_detail = prob_det.strip()
            changes.append(f"Detail: {ticket.problem_detail}")

    if ticket.status == Ticket.Status.CLOSED and not ticket.closed_at:
        ticket.closed_at = timezone.now()
    elif ticket.status != Ticket.Status.CLOSED:
        ticket.closed_at = None

    if changes:
        ticket.save()
        ActivityLog.record(
            request.user, ActivityLog.Verb.TICKET_UPDATE,
            target_label=ticket.number, subject=ticket.subject,
            status=ticket.get_status_display(),
            pic=ticket.requester_phone if ticket.requester_phone else "No PIC number",
            reason=" · ".join(changes), url=ticket.get_absolute_url(),
        )
        messages.success(request, "Ticket properties updated.")
    else:
        messages.info(request, "No changes made.")

    return redirect(ticket)


@login_required
@require_POST
def ticket_close(request, number):
    ticket = get_object_or_404(Ticket, number=number)
    if _locked(request, ticket):
        return redirect(ticket)
    form = CloseTicketForm(request.POST)

    if not form.is_valid():
        messages.error(request, "Incomplete closing form fields.")
        return redirect(ticket)

    if ticket.ticket_type == Ticket.Type.RELOCATION:
        action = form.cleaned_data.get("relocation_action") or "Relokasi"
        new_site = form.cleaned_data.get("new_site", "").strip()
        new_address = form.cleaned_data.get("new_address", "").strip()
        reason = form.cleaned_data.get("reason", "").strip()

        ticket.relocation_action = action
        if action == "Relokasi":
            if not new_site or not new_address:
                messages.error(request, "New site and New address are required for Relocation.")
                return redirect(ticket)
            ticket.new_site = new_site
            ticket.new_address = new_address
            close_summary = f"Relocated to Site {new_site} ({new_address})"
        else:
            ticket.new_site = ""
            ticket.new_address = ""
            close_summary = "Dismantle"

        if reason:
            close_summary += f" — {reason}"

        category_label = action
        ticket.close_reason = close_summary
    else:
        category = form.cleaned_data.get("reason_category")
        reason = form.cleaned_data.get("reason", "").strip()
        if not category or not reason:
            messages.error(request, "Resolution category and closing note are required.")
            return redirect(ticket)
        category_label = category
        ticket.close_reason = f"{category} — {reason}"

        if ticket.ticket_type == Ticket.Type.PROBLEM:
            prob_cat = form.cleaned_data.get("problem_category")
            if prob_cat:
                ticket.problem_category = prob_cat
                prob_det = form.cleaned_data.get("problem_detail", "").strip()
                ticket.problem_detail = prob_det

    ticket.status = Ticket.Status.CLOSED
    ticket.closed_at = timezone.now()
    ticket.save()

    ActivityLog.record(
        request.user, ActivityLog.Verb.TICKET_CLOSE,
        target_label=ticket.number, subject=ticket.subject,
        status=ticket.get_status_display(),
        pic=ticket.requester_phone if ticket.requester_phone else "No PIC number",
        reason=ticket.close_reason, url=ticket.get_absolute_url(),
    )
    Notification.objects.create(
        title=f"Ticket {ticket.number} closed",
        body=f"{ticket.subject} · {category_label}",
        url=ticket.get_absolute_url(), actor=request.user,
        level=Notification.Level.SUCCESS,
    )
    messages.success(request, f"Ticket {ticket.number} closed. Duration {ticket.duration_display}.")

    return redirect(ticket)


@login_required
@require_POST
def ticket_reopen(request, number):
    ticket = get_object_or_404(Ticket, number=number)
    if _locked(request, ticket):
        return redirect(ticket)
    ticket.status = Ticket.Status.OUTSTANDING
    ticket.closed_at = None
    ticket.save()

    ActivityLog.record(
        request.user, ActivityLog.Verb.TICKET_REOPEN,
        target_label=ticket.number, subject=ticket.subject,
        status=ticket.get_status_display(),
        pic=ticket.requester_phone if ticket.requester_phone else "No PIC number",
        reason="Ticket reopened by user", url=ticket.get_absolute_url(),
    )
    Notification.objects.create(
        title=f"Ticket {ticket.number} reopened",
        body=f"{ticket.subject} · Outstanding",
        url=ticket.get_absolute_url(), actor=request.user,
        level=Notification.Level.WARNING,
    )
    messages.warning(request, f"Ticket {ticket.number} reopened as Outstanding.")
    return redirect(ticket)


@login_required
@require_POST
def ticket_delete(request, number):
    ticket = get_object_or_404(Ticket, number=number)
    if not (request.user.is_superuser or request.user.is_staff):
        messages.error(request, "Only administrators have permission to delete tickets.")
        return redirect(ticket)

    ticket_number = ticket.number
    ticket_subject = ticket.subject
    ActivityLog.record(
        request.user, ActivityLog.Verb.TICKET_DELETE,
        target_label=ticket_number, subject=ticket_subject,
        status="Deleted", pic=request.user.display_name,
        reason=f"Permanently deleted by {request.user.display_name}",
    )
    ticket.delete()
    messages.success(request, f"Ticket {ticket_number} has been permanently deleted.")
    return redirect("tickets:list")


@login_required
@require_POST
def ticket_bulk(request):
    """Bulk actions from ticket list — assign, update status, close."""
    numbers = request.POST.getlist("selected")
    action = request.POST.get("action", "")
    tickets = Ticket.objects.filter(number__in=numbers)
    count = tickets.count()

    if not count:
        messages.warning(request, "No tickets selected.")
        return redirect("tickets:list")

    editable = [t for t in tickets if t.can_edit(request.user)]
    skipped = count - len(editable)

    if action.startswith("status:"):
        value = action.split(":", 1)[1]
        if value in dict(Ticket.Status.choices):
            for ticket in editable:
                if ticket.status == value:
                    continue
                ticket.status = value
                ticket.closed_at = (timezone.now() if value == Ticket.Status.CLOSED
                                    else None)
                ticket.save()
                ActivityLog.record(
                    request.user, ActivityLog.Verb.TICKET_UPDATE,
                    target_label=ticket.number, subject=ticket.subject,
                    status=ticket.get_status_display(),
                    pic=ticket.requester_phone if ticket.requester_phone else "No PIC number",
                    reason="Bulk update from ticket list",
                    url=ticket.get_absolute_url(),
                )
            messages.success(request, f"{len(editable)} ticket(s) updated to "
                                      f"{dict(Ticket.Status.choices)[value]}.")
    elif action == "assign:me":
        for ticket in editable:
            ticket.assignee = request.user
            ticket.save()
        messages.success(request, f"{len(editable)} ticket(s) assigned to you.")
    else:
        messages.warning(request, "Please select an action first.")
        skipped = 0

    if skipped:
        messages.warning(request, f"{skipped} closed ticket(s) skipped because they are "
                                  "locked (admin only).")

    back = request.POST.get("next")
    return redirect(back or "tickets:list")


# ── Company / Corporate Management (Admin Only) ─────────────────────────────

@login_required
def company_list(request):
    """Admin-only management page for corporate clients / companies."""
    if not (request.user.is_staff or request.user.is_superuser):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied("Only administrators can manage companies.")

    if request.method == "POST":
        form = CompanyForm(request.POST)
        if form.is_valid():
            company = form.save()
            ActivityLog.record(
                request.user, ActivityLog.Verb.TICKET_UPDATE,
                target_label=company.name, subject=f"Added new corporate partner: {company.name}",
                reason="Created company master record",
            )
            messages.success(request, f"Company '{company.name}' added successfully.")
            return redirect("tickets:company_list")
        else:
            messages.error(request, "Please check the form inputs.")
    else:
        form = CompanyForm()

    qs = Company.objects.prefetch_related("services").all()
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(name__icontains=q) |
            Q(code__icontains=q) |
            Q(customer_id__icontains=q) |
            Q(partner__icontains=q) |
            Q(contact_person__icontains=q)
        )

    companies = list(qs)
    # Calculate ticket counts per company
    ticket_counts = dict(
        Ticket.objects.values("company")
        .annotate(total=Count("id"))
        .values_list("company", "total")
    )
    for c in companies:
        c.total_tickets = ticket_counts.get(c.name, 0)
        c.active_services = list(c.services.all())
        c.total_services = len(c.active_services)

    ctx = {
        "page_title": "Companies",
        "breadcrumb": [("Companies", None)],
        "companies": companies,
        "form": form,
        "service_form": CompanyServiceForm(),
        "query": q,
        "total_count": len(companies),
        "active_count": sum(1 for c in companies if c.is_active),
        "inactive_count": sum(1 for c in companies if not c.is_active),
    }
    return render(request, "tickets/company_list.html", ctx)


@login_required
def company_edit(request, pk):
    """Admin-only edit page for a company."""
    if not (request.user.is_staff or request.user.is_superuser):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied("Only administrators can manage companies.")

    company = get_object_or_404(Company, pk=pk)
    old_name = company.name

    if request.method == "POST":
        form = CompanyForm(request.POST, instance=company)
        if form.is_valid():
            updated = form.save()
            if old_name != updated.name:
                Ticket.objects.filter(company=old_name).update(company=updated.name)
            messages.success(request, f"Company '{updated.name}' updated successfully.")
            return redirect("tickets:company_list")
    else:
        form = CompanyForm(instance=company)

    ctx = {
        "page_title": f"Edit {company.name}",
        "breadcrumb": [("Companies", reverse("tickets:company_list")), ("Edit", None)],
        "company": company,
        "form": form,
        "services": company.services.all(),
        "service_form": CompanyServiceForm(),
    }
    return render(request, "tickets/company_form.html", ctx)


@login_required
@require_POST
def company_service_create(request, company_pk):
    """Add a service under a corporate client."""
    if not (request.user.is_staff or request.user.is_superuser):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied("Only administrators can manage company services.")

    company = get_object_or_404(Company, pk=company_pk)
    service_id = request.POST.get("service_id", "").strip()
    service_name = request.POST.get("service_name", "").strip()
    device_solution = request.POST.get("device_solution", "").strip()
    brand = request.POST.get("brand", "").strip()

    if not service_name:
        messages.error(request, "Service / Product name is required.")
    else:
        CompanyService.objects.create(
            company=company,
            service_id=service_id,
            service_name=service_name,
            device_solution=device_solution,
            brand=brand,
        )
        messages.success(request, f"Service '{service_name}' added to {company.name}.")

    next_url = request.POST.get("next")
    return redirect(next_url or "tickets:company_list")


@login_required
@require_POST
def company_service_delete(request, pk):
    """Delete a company service."""
    if not (request.user.is_staff or request.user.is_superuser):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied("Only administrators can manage company services.")

    service = get_object_or_404(CompanyService, pk=pk)
    comp_name = service.company.name
    s_name = service.service_name
    service.delete()
    messages.success(request, f"Service '{s_name}' removed from {comp_name}.")
    next_url = request.POST.get("next")
    return redirect(next_url or "tickets:company_list")


@login_required
def companies_data_api(request):
    """API returning active companies and their services for frontend dynamic forms."""
    return JsonResponse(json.loads(_get_companies_data_json()))


@login_required
@require_POST
def company_toggle(request, pk):
    """Toggle active status of a company."""
    if not (request.user.is_staff or request.user.is_superuser):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied("Only administrators can manage companies.")

    company = get_object_or_404(Company, pk=pk)
    company.is_active = not company.is_active
    company.save(update_fields=["is_active", "updated_at"])
    status_str = "activated" if company.is_active else "deactivated"
    messages.success(request, f"Company '{company.name}' {status_str}.")
    return redirect("tickets:company_list")


@login_required
@require_POST
def company_delete(request, pk):
    """Delete a company if it has 0 tickets, or warn user."""
    if not (request.user.is_staff or request.user.is_superuser):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied("Only administrators can manage companies.")

    company = get_object_or_404(Company, pk=pk)
    ticket_count = Ticket.objects.filter(company=company.name).count()
    if ticket_count > 0:
        messages.error(request, f"Cannot delete '{company.name}' because {ticket_count} ticket(s) are associated with it. Please deactivate it instead.")
    else:
        company.delete()
        messages.success(request, f"Company '{company.name}' deleted successfully.")
    return redirect("tickets:company_list")
