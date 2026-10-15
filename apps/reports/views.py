from io import BytesIO

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone

from apps.core import charts, periods
from apps.core.models import ActivityLog
from apps.tickets.models import Ticket

from . import excel
from .models import ReportExport

def _agent_performance(scope, sort):
    """Progres tiket per agent — dari open sampai close."""
    rows = (
        scope.filter(assignee__isnull=False)
        .values("assignee__id", "assignee__first_name", "assignee__last_name",
                "assignee__username", "assignee__position")
        .annotate(
            total=Count("id"),
            open=Count("id", filter=Q(status=Ticket.Status.OPEN)),
            outstanding=Count("id", filter=Q(status=Ticket.Status.OUTSTANDING)),
            closed=Count("id", filter=Q(status=Ticket.Status.CLOSED)),
        )
    )

    agents = []
    for row in rows:
        name = f"{row['assignee__first_name']} {row['assignee__last_name']}".strip()
        name = name or row["assignee__username"]
        parts = [p for p in name.split() if p]
        agents.append({
            "id": row["assignee__id"],
            "name": name,
            "initials": "".join(p[0] for p in parts[:2]).upper(),
            "position": row["assignee__position"] or "Agent",
            "total": row["total"],
            "open": row["open"],
            "outstanding": row["outstanding"],
            "closed": row["closed"],
            "rate": round(row["closed"] * 100 / row["total"]) if row["total"] else 0,
            "bar": charts.stacked_bar([
                ("open", "Open", row["open"]),
                ("outstanding", "Outstanding", row["outstanding"]),
                ("closed", "Close", row["closed"]),
            ], total=row["total"]),
        })

    keys = {
        "total": lambda a: -a["total"],
        "open": lambda a: -a["open"],
        "outstanding": lambda a: -a["outstanding"],
        "closed": lambda a: -a["closed"],
        "rate": lambda a: -a["rate"],
        "name": lambda a: a["name"].lower(),
    }
    agents.sort(key=keys.get(sort, keys["total"]))
    return agents


def _report_context(request):
    """Konteks bersama halaman pratinjau dan berkas Excel.

    Dipakai keduanya supaya angka yang dilihat di layar dijamin sama dengan
    angka yang keluar di file — bukan dua perhitungan terpisah.
    """
    period = request.GET.get("period", "daily")
    if period not in dict(ReportExport.Period.choices):
        period = "daily"

    default_preset = "this_month" if period == "monthly" else "today"
    date_range = periods.resolve(request, default=default_preset)

    scope = (Ticket.objects.in_range(date_range.start, date_range.end)
             .select_related("assignee"))

    company = request.GET.get("company", "").strip()
    if company:
        scope = scope.filter(company=company)

    counts = scope.aggregate(
        total=Count("id"),
        open=Count("id", filter=Q(status=Ticket.Status.OPEN)),
        outstanding=Count("id", filter=Q(status=Ticket.Status.OUTSTANDING)),
        closed=Count("id", filter=Q(status=Ticket.Status.CLOSED)),
    )

    return {
        "period": period,
        "period_label": dict(ReportExport.Period.choices)[period],
        "range": date_range,
        "range_label": date_range.label,
        "company": company,
        "counts": counts,
        "type_counts": {
            "problem": scope.filter(ticket_type=Ticket.Type.PROBLEM).count(),
            "feature": scope.filter(ticket_type=Ticket.Type.FEATURE).count(),
            "relocation": scope.filter(ticket_type=Ticket.Type.RELOCATION).count(),
        },
        "tickets": list(scope),
        "agents": _agent_performance(scope, "total"),
        "donut": charts.donut([
            ("open", "Open", counts["open"]),
            ("outstanding", "Outstanding", counts["outstanding"]),
            ("closed", "Close", counts["closed"]),
        ]),
    }


@login_required
def export_page(request):
    from apps.tickets.models import Company
    try:
        company_choices = list(Company.objects.filter(is_active=True).order_by("name").values_list("name", "name"))
        if not company_choices:
            company_choices = [(c, c) for c in Ticket.DEFAULT_COMPANIES]
    except Exception:
        company_choices = [(c, c) for c in Ticket.DEFAULT_COMPANIES]

    ctx = _report_context(request)
    ctx.update({
        "page_title": "Analytics & Export",
        "breadcrumb": [("Analytics & Export", None)],
        "presets": periods.PRESETS,
        "period_choices": ReportExport.Period.choices,
        "companies": company_choices,
        "preview": ctx["tickets"][:12],
        "has_rc": any(t.ticket_type == Ticket.Type.RELOCATION for t in ctx["tickets"]),
        "history": ReportExport.objects.select_related("created_by")[:8],
        "sheets": [
            ("Ticket Details", "One row per ticket with all standard columns"),
            ("Summary", "Total count & percentage per status, breakdown by ticket type"),
        ] + ([("Agent Performance", "Open / Outstanding / Close metrics and completion rate per agent")]
             if (request.user.is_staff or request.user.is_superuser) else []),
    })
    return render(request, "reports/export.html", ctx)


@login_required
def export_download(request):
    ctx = _report_context(request)
    ctx["author"] = request.user.display_name

    report_type = request.GET.get("type", "detail")
    if report_type == "agent" and not (request.user.is_staff or request.user.is_superuser):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied("Only administrators can download agent performance reports.")
    workbook = excel.build_workbook(ctx, report_type)
    buffer = BytesIO()
    workbook.save(buffer)
    buffer.seek(0)

    name = excel.file_name(ctx["period"], ctx["range"], report_type)

    ReportExport.objects.create(
        period=ctx["period"],
        date_from=ctx["range"].start_date,
        date_to=ctx["range"].end_date,
        file_name=name,
        row_count=len(ctx["tickets"]),
        created_by=request.user,
        created_at=timezone.now(),
    )
    ActivityLog.record(
        request.user, ActivityLog.Verb.REPORT_EXPORT,
        target_label=name, subject=f"{ctx['period_label']} Report",
        status="Completed", pic=request.user.display_name,
        reason=f"Range {ctx['range'].label} · {len(ctx['tickets'])} tickets",
    )

    response = HttpResponse(
        buffer.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = f'attachment; filename="{name}"'
    return response
