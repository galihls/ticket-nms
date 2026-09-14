from io import BytesIO

from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone

from apps.core import charts, periods
from apps.core.models import ActivityLog
from apps.core.views import admin_required, _agent_performance
from apps.tickets.models import Ticket

from . import excel
from .models import ReportExport


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

    site = request.GET.get("site", "").strip()
    if site:
        scope = scope.filter(site_code__icontains=site)

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
        "site": site,
        "counts": counts,
        "type_counts": {
            "problem": scope.filter(ticket_type=Ticket.Type.PROBLEM).count(),
            "feature": scope.filter(ticket_type=Ticket.Type.FEATURE).count(),
        },
        "tickets": list(scope),
        "agents": _agent_performance(scope, "total"),
        "donut": charts.donut([
            ("open", "Open", counts["open"]),
            ("outstanding", "Outstanding", counts["outstanding"]),
            ("closed", "Close", counts["closed"]),
        ]),
    }


@admin_required
def export_page(request):
    ctx = _report_context(request)
    ctx.update({
        "page_title": "Analytics & Export",
        "breadcrumb": [("Analytics & Export", None)],
        "presets": periods.PRESETS,
        "period_choices": ReportExport.Period.choices,
        "preview": ctx["tickets"][:12],
        "history": ReportExport.objects.select_related("created_by")[:8],
        "sheets": [
            ("Rekap", "Jumlah & persentase per status, rincian per tipe tiket"),
            ("Detail Tiket", "Satu baris per tiket: nomor, site, PIC, durasi, alasan close"),
            ("Performa Agent", "Open / Outstanding / Close dan rasio selesai per agent"),
        ],
    })
    return render(request, "reports/export.html", ctx)


@admin_required
def export_download(request):
    ctx = _report_context(request)
    ctx["author"] = request.user.display_name

    workbook = excel.build_workbook(ctx)
    buffer = BytesIO()
    workbook.save(buffer)
    buffer.seek(0)

    name = excel.file_name(ctx["period"], ctx["range"])

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
        target_label=name, subject=f"Laporan {ctx['period_label']}",
        status="Selesai", pic=request.user.display_name,
        reason=f"Rentang {ctx['range'].label} · {len(ctx['tickets'])} tiket",
    )

    response = HttpResponse(
        buffer.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = f'attachment; filename="{name}"'
    return response
