from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import models
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.accounts.models import User
from apps.core import periods
from apps.core.models import ActivityLog, Notification

from .forms import GROUPS, CloseTicketForm, ReplyForm, TicketForm
from .models import Ticket, TicketReply

SORTS = [
    ("-opened_at", "Terbaru dibuat"),
    ("opened_at", "Terlama dibuat"),
    ("-updated_at", "Terakhir diperbarui"),
    ("priority", "Prioritas"),
    ("due_at", "Jatuh tempo terdekat"),
    ("number", "Nomor tiket"),
]


@login_required
def ticket_list(request):
    qs = Ticket.objects.select_related("assignee")

    status = request.GET.getlist("status")
    ticket_type = request.GET.getlist("type")
    priority = request.GET.getlist("priority")
    assignee = request.GET.get("assignee", "")
    group = request.GET.get("group", "")
    q = request.GET.get("q", "").strip()
    sort = request.GET.get("sort", "-opened_at")

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
        order = {"urgent": 0, "high": 1, "medium": 2, "low": 3}
        qs = sorted(qs, key=lambda t: (order.get(t.priority, 9), -t.id))
    elif sort == "due_at":
        # Tiket tanpa jatuh tempo ditaruh di belakang, bukan di depan
        qs = qs.order_by(models.F("due_at").asc(nulls_last=True))
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

    return render(request, "tickets/list.html", {
        "page_title": "Daftar Tiket",
        "breadcrumb": [("Daftar Tiket", None)],
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
            "assignee": assignee, "group": group, "sort": sort, "q": q,
        },
        "range": date_range,
        "presets": periods.PRESETS,
        "has_filter": any([status, ticket_type, priority, assignee, group, q, date_range]),
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
        "breadcrumb": [("Daftar Tiket", reverse("tickets:list")), (ticket.number, None)],
        "ticket": ticket,
        "replies": ticket.replies.select_related("author"),
        "reply_form": ReplyForm(),
        "close_form": CloseTicketForm(),
        "statuses": Ticket.Status.choices,
        "priorities": Ticket.Priority.choices,
        "types": Ticket.Type.choices,
        "groups": GROUPS,
        "agents": User.objects.filter(is_active=True),
        "history": ActivityLog.objects.filter(target_label=ticket.number)[:20],
        "related": Ticket.objects.filter(site_code=ticket.site_code)
                                .exclude(pk=ticket.pk)[:4] if ticket.site_code else [],
    })


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
        if not ticket.requester_name:
            ticket.requester_name = request.user.display_name
        ticket.save()

        ActivityLog.record(
            request.user, ActivityLog.Verb.TICKET_CREATE,
            target_label=ticket.number, subject=ticket.subject,
            status=ticket.get_status_display(),
            pic=ticket.assignee.display_name if ticket.assignee else "Belum ditugaskan",
            url=ticket.get_absolute_url(),
        )
        Notification.objects.create(
            title=f"Tiket baru {ticket.number}",
            body=f"{ticket.subject} · {ticket.get_priority_display()}",
            url=ticket.get_absolute_url(), actor=request.user,
            level=(Notification.Level.DANGER
                   if ticket.priority == Ticket.Priority.URGENT
                   else Notification.Level.INFO),
        )
        messages.success(request, f"Tiket {ticket.number} berhasil dibuat.")
        return redirect(ticket)

    if request.method == "POST":
        messages.error(request, "Periksa kembali isian yang ditandai merah.")

    return render(request, "tickets/form.html", {
        "page_title": "Buat Tiket Baru",
        "breadcrumb": [("Daftar Tiket", reverse("tickets:list")), ("Buat Tiket", None)],
        "form": form,
        "number_preview": Ticket.next_number(preview_type),
        "preview_type": preview_type,
        "is_edit": False,
    })


@login_required
def ticket_edit(request, number):
    ticket = get_object_or_404(Ticket, number=number)
    form = TicketForm(request.POST or None, instance=ticket)

    if request.method == "POST" and form.is_valid():
        form.save()
        ActivityLog.record(
            request.user, ActivityLog.Verb.TICKET_UPDATE,
            target_label=ticket.number, subject=ticket.subject,
            status=ticket.get_status_display(),
            pic=ticket.assignee.display_name if ticket.assignee else "Belum ditugaskan",
            url=ticket.get_absolute_url(),
        )
        messages.success(request, f"Perubahan tiket {ticket.number} tersimpan.")
        return redirect(ticket)

    return render(request, "tickets/form.html", {
        "page_title": f"Ubah {ticket.number}",
        "breadcrumb": [("Daftar Tiket", reverse("tickets:list")),
                       (ticket.number, ticket.get_absolute_url()), ("Ubah", None)],
        "form": form,
        "ticket": ticket,
        "number_preview": ticket.number,
        "preview_type": ticket.ticket_type,
        "is_edit": True,
    })


@login_required
@require_POST
def ticket_reply(request, number):
    ticket = get_object_or_404(Ticket, number=number)
    form = ReplyForm(request.POST)

    if form.is_valid():
        reply = form.save(commit=False)
        reply.ticket = ticket
        reply.author = request.user
        reply.author_label = request.user.display_name
        reply.save()

        if not ticket.first_response_at:
            ticket.first_response_at = timezone.now()
        # Membalas tiket yang masih Open berarti sudah ditangani
        if ticket.status == Ticket.Status.OPEN and not reply.is_private:
            ticket.status = Ticket.Status.OUTSTANDING
        ticket.save()

        verb = (ActivityLog.Verb.TICKET_NOTE if reply.is_private
                else ActivityLog.Verb.TICKET_REPLY)
        ActivityLog.record(
            request.user, verb, target_label=ticket.number, subject=ticket.subject,
            status=ticket.get_status_display(),
            pic=ticket.assignee.display_name if ticket.assignee else "Belum ditugaskan",
            reason=reply.body[:200], url=ticket.get_absolute_url(),
        )
        messages.success(request, "Catatan internal ditambahkan." if reply.is_private
                         else "Balasan terkirim.")
    else:
        messages.error(request, "Balasan tidak boleh kosong.")

    return redirect(ticket)


@login_required
@require_POST
def ticket_update_properties(request, number):
    """Panel properti di halaman detail — ubah status, prioritas, PIC, grup."""
    ticket = get_object_or_404(Ticket, number=number)
    changes = []

    field_map = {
        "status": (Ticket.Status, "Status"),
        "priority": (Ticket.Priority, "Prioritas"),
        "ticket_type": (Ticket.Type, "Tipe"),
    }
    for field, (choices, label) in field_map.items():
        value = request.POST.get(field)
        if value and value in dict(choices.choices) and value != getattr(ticket, field):
            old = getattr(ticket, f"get_{field}_display")()
            setattr(ticket, field, value)
            changes.append(f"{label}: {old} → {getattr(ticket, f'get_{field}_display')()}")

    assignee_id = request.POST.get("assignee")
    if assignee_id is not None:
        new_assignee = (User.objects.filter(pk=assignee_id).first()
                        if assignee_id else None)
        if new_assignee != ticket.assignee:
            old = ticket.assignee.display_name if ticket.assignee else "Belum ditugaskan"
            ticket.assignee = new_assignee
            new = new_assignee.display_name if new_assignee else "Belum ditugaskan"
            changes.append(f"PIC: {old} → {new}")

    group = request.POST.get("group")
    if group is not None and group != ticket.group:
        changes.append(f"Grup: {ticket.group or '—'} → {group or '—'}")
        ticket.group = group

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
            pic=ticket.assignee.display_name if ticket.assignee else "Belum ditugaskan",
            reason=" · ".join(changes), url=ticket.get_absolute_url(),
        )
        messages.success(request, "Properti tiket diperbarui.")
    else:
        messages.info(request, "Tidak ada perubahan.")

    return redirect(ticket)


@login_required
@require_POST
def ticket_close(request, number):
    ticket = get_object_or_404(Ticket, number=number)
    form = CloseTicketForm(request.POST)

    if not form.is_valid():
        messages.error(request, "Alasan close wajib diisi.")
        return redirect(ticket)

    category = form.cleaned_data["reason_category"]
    reason = form.cleaned_data["reason"]

    ticket.status = Ticket.Status.CLOSED
    ticket.closed_at = timezone.now()
    ticket.close_reason = f"{category} — {reason}"
    ticket.save()

    ActivityLog.record(
        request.user, ActivityLog.Verb.TICKET_CLOSE,
        target_label=ticket.number, subject=ticket.subject,
        status=ticket.get_status_display(),
        pic=ticket.assignee.display_name if ticket.assignee else "Belum ditugaskan",
        reason=ticket.close_reason, url=ticket.get_absolute_url(),
    )
    Notification.objects.create(
        title=f"Tiket {ticket.number} ditutup",
        body=f"{ticket.subject} · {category}",
        url=ticket.get_absolute_url(), actor=request.user,
        level=Notification.Level.SUCCESS,
    )
    messages.success(request, f"Tiket {ticket.number} ditutup. Durasi {ticket.duration_display}.")

    if form.cleaned_data.get("create_article"):
        url = reverse("solutions:create")
        return redirect(f"{url}?dari={ticket.number}")
    return redirect(ticket)


@login_required
@require_POST
def ticket_reopen(request, number):
    ticket = get_object_or_404(Ticket, number=number)
    ticket.status = Ticket.Status.OUTSTANDING
    ticket.closed_at = None
    ticket.save()

    ActivityLog.record(
        request.user, ActivityLog.Verb.TICKET_REOPEN,
        target_label=ticket.number, subject=ticket.subject,
        status=ticket.get_status_display(),
        pic=ticket.assignee.display_name if ticket.assignee else "Belum ditugaskan",
        reason=request.POST.get("reason", "Dibuka ulang oleh agent"),
        url=ticket.get_absolute_url(),
    )
    messages.success(request, f"Tiket {ticket.number} dibuka ulang.")
    return redirect(ticket)


@login_required
@require_POST
def ticket_bulk(request):
    """Aksi massal dari daftar tiket — tugaskan, ubah status, tutup."""
    numbers = request.POST.getlist("selected")
    action = request.POST.get("action", "")
    tickets = Ticket.objects.filter(number__in=numbers)
    count = tickets.count()

    if not count:
        messages.warning(request, "Tidak ada tiket yang dipilih.")
        return redirect("tickets:list")

    if action.startswith("status:"):
        value = action.split(":", 1)[1]
        if value in dict(Ticket.Status.choices):
            for ticket in tickets:
                ticket.status = value
                ticket.closed_at = (timezone.now() if value == Ticket.Status.CLOSED
                                    else None)
                ticket.save()
                ActivityLog.record(
                    request.user, ActivityLog.Verb.TICKET_UPDATE,
                    target_label=ticket.number, subject=ticket.subject,
                    status=ticket.get_status_display(),
                    pic=ticket.assignee.display_name if ticket.assignee else "Belum ditugaskan",
                    reason="Perubahan massal dari daftar tiket",
                    url=ticket.get_absolute_url(),
                )
            messages.success(request, f"{count} tiket diubah menjadi "
                                      f"{dict(Ticket.Status.choices)[value]}.")
    elif action == "assign:me":
        for ticket in tickets:
            ticket.assignee = request.user
            ticket.save()
        messages.success(request, f"{count} tiket ditugaskan ke Anda.")
    else:
        messages.warning(request, "Pilih aksi terlebih dahulu.")

    back = request.POST.get("next")
    return redirect(back or "tickets:list")
