from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from apps.solutions.models import Article
from apps.tickets.models import Ticket

from . import charts, periods
from .models import ActivityLog, Notification

admin_required = user_passes_test(
    lambda u: u.is_authenticated and (u.is_superuser or u.is_staff),
    login_url="core:forbidden",
)


@login_required
def dashboard(request):
    """Ringkasan operasional. Semua angka mengikuti filter kalender."""
    date_range = periods.resolve(request)
    scope = Ticket.objects.in_range(date_range.start, date_range.end)

    counts = scope.aggregate(
        total=Count("id"),
        open=Count("id", filter=Q(status=Ticket.Status.OPEN)),
        outstanding=Count("id", filter=Q(status=Ticket.Status.OUTSTANDING)),
        closed=Count("id", filter=Q(status=Ticket.Status.CLOSED)),
    )

    # Pembanding periode sebelumnya, panjang rentang sama
    prev = date_range.previous
    prev_total = Ticket.objects.in_range(prev.start, prev.end).count()
    delta = counts["total"] - prev_total
    delta_percent = round(delta * 100 / prev_total) if prev_total else None

    status_rows = [
        ("open", "Open", counts["open"]),
        ("outstanding", "Outstanding", counts["outstanding"]),
        ("closed", "Closed", counts["closed"]),
    ]

    problem_counts = scope.filter(ticket_type=Ticket.Type.PROBLEM).aggregate(
        power=Count("id", filter=Q(problem_category=Ticket.ProblemCategory.POWER)),
        los=Count("id", filter=Q(problem_category=Ticket.ProblemCategory.LOS)),
        other=Count("id", filter=Q(problem_category=Ticket.ProblemCategory.OTHER)),
    )
    problem_rows = [
        ("power", "Power Outage", problem_counts["power"]),
        ("los", "Internet LOS", problem_counts["los"]),
        ("other", "Other", problem_counts["other"]),
    ]

    context = {
        "page_title": "Dashboard",
        "breadcrumb": [("Dashboard", None)],
        "range": date_range,
        "presets": periods.PRESETS,
        "counts": counts,
        "delta": delta,
        "delta_percent": delta_percent,
        "prev_total": prev_total,
        "donut": charts.donut(status_rows),
        "problem_donut": charts.donut(problem_rows),
        "type_counts": {
            "problem": scope.filter(ticket_type=Ticket.Type.PROBLEM).count(),
            "feature": scope.filter(ticket_type=Ticket.Type.FEATURE).count(),
            "relocation": scope.filter(ticket_type=Ticket.Type.RELOCATION).count(),
        },
        "urgent_tickets": Ticket.objects.high_priority()
                                       .select_related("assignee")[:5],
        "activities": ActivityLog.objects.select_related("actor")[:4],
        "top_articles": Article.objects.published().select_related("author")
                                       .order_by("-views")[:4],
    }
    return render(request, "core/dashboard.html", context)


@admin_required
def activity_log(request):
    """Audit trail penuh — akses admin."""
    logs = ActivityLog.objects.select_related("actor")
    verb = request.GET.get("verb", "")
    actor = request.GET.get("actor", "")
    q = request.GET.get("q", "").strip()

    if verb:
        logs = logs.filter(verb=verb)
    if actor:
        logs = logs.filter(actor_id=actor)
    if q:
        logs = logs.filter(Q(subject__icontains=q) | Q(actor_label__icontains=q)
                           | Q(target_label__icontains=q))

    page = Paginator(logs, 25).get_page(request.GET.get("page"))

    from apps.accounts.models import User
    return render(request, "core/activity_log.html", {
        "page_title": "Activity Log",
        "breadcrumb": [("Activity Log", None)],
        "page_obj": page,
        "verbs": ActivityLog.Verb.choices,
        "actors": User.objects.filter(is_active=True),
        "selected_verb": verb,
        "selected_actor": actor,
        "q": q,
    })


@login_required
def notifications(request):
    notes = Notification.objects.select_related("actor")
    if request.GET.get("filter") == "unread":
        notes = notes.filter(is_read=False)
    page = Paginator(notes, 20).get_page(request.GET.get("page"))
    return render(request, "core/notifications.html", {
        "page_title": "Notifications",
        "breadcrumb": [("Notifications", None)],
        "page_obj": page,
        "filter": request.GET.get("filter", "all"),
    })


@login_required
@require_POST
def notifications_read(request):
    count = Notification.objects.filter(is_read=False).update(is_read=True)
    messages.success(request, f"{count} notifications marked as read.")
    return redirect(request.POST.get("next") or "core:notifications")


@login_required
def search(request):
    """Pencarian global dari topbar — tiket dan artikel solusi."""
    q = request.GET.get("q", "").strip()
    tickets = articles = []
    if q:
        tickets = (Ticket.objects.filter(
            Q(number__icontains=q) | Q(subject__icontains=q)
            | Q(requester_name__icontains=q) | Q(site_code__icontains=q)
            | Q(description__icontains=q)
        ).select_related("assignee")[:25])
        articles = (Article.objects.published().filter(
            Q(title__icontains=q) | Q(body__icontains=q) | Q(tags__icontains=q)
        ).select_related("author")[:10])

    return render(request, "core/search.html", {
        "page_title": "Search Results",
        "breadcrumb": [("Search", None)],
        "q": q,
        "tickets": tickets,
        "articles": articles,
        "result_count": len(tickets) + len(articles),
    })


@login_required
def styleguide(request):
    """Katalog komponen UI — acuan internal supaya tampilan tetap konsisten."""
    return render(request, "core/styleguide.html", {
        "page_title": "Component Styleguide",
        "breadcrumb": [("Component Styleguide", None)],
        "donut_demo": charts.donut([
            ("open", "Open", 12), ("outstanding", "Outstanding", 7), ("closed", "Close", 31),
        ]),
    })


@login_required
def forbidden(request):
    return render(request, "core/403.html", {
        "page_title": "Access Denied",
        "breadcrumb": [("Access Denied", None)],
        "back_url": reverse("core:dashboard"),
    }, status=403)


def healthz(request):
    """Endpoint cek hidup untuk monitoring/load balancer."""
    from django.db import connection

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        return JsonResponse({"status": "ok"})
    except Exception as exc:  # pragma: no cover - jalur kegagalan infrastruktur
        return JsonResponse({"status": "error", "detail": str(exc)}, status=503)
