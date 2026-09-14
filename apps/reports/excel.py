"""Builder Excel laporan harian & bulanan.

Format mengacu pada `Report Monitoring INITECH 2026.xlsx`. Selama file acuan
belum diterima, struktur sheet di sini adalah pendekatan terbaik dari
kebutuhan: satu sheet rekap, satu sheet detail tiket, satu sheet performa
agent. Kolomnya tinggal digeser kalau file acuan sudah ada.
"""

from django.utils import timezone
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

NAVY = "16294F"
NAVY_SOFT = "EDF1F8"
LINE = "E3E8EF"

STATUS_FILL = {
    "Open": "EBF2FE",
    "Outstanding": "FEF3E8",
    "Close": "E7F6EE",
}

_thin = Side(style="thin", color=LINE)
BORDER = Border(left=_thin, right=_thin, top=_thin, bottom=_thin)


def _title_block(ws, title, subtitle, width):
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=width)
    cell = ws.cell(row=1, column=1, value=title)
    cell.font = Font(bold=True, size=14, color=NAVY)
    cell.alignment = Alignment(horizontal="left", vertical="center")
    ws.row_dimensions[1].height = 24

    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=width)
    sub = ws.cell(row=2, column=1, value=subtitle)
    sub.font = Font(size=9, color="667085")


def _header_row(ws, row, headers, widths=None):
    for col, name in enumerate(headers, start=1):
        cell = ws.cell(row=row, column=col, value=name)
        cell.font = Font(bold=True, size=10, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor=NAVY)
        cell.alignment = Alignment(horizontal="center", vertical="center",
                                   wrap_text=True)
        cell.border = BORDER
    ws.row_dimensions[row].height = 26
    for col, width in enumerate(widths or [], start=1):
        ws.column_dimensions[get_column_letter(col)].width = width
    ws.freeze_panes = ws.cell(row=row + 1, column=1)


def _sheet_rekap(wb, ctx):
    ws = wb.create_sheet("Rekap")
    _title_block(ws, f"Rekap {ctx['period_label']}", ctx["range_label"], 4)

    _header_row(ws, 4, ["Status", "Jumlah Tiket", "Persentase", "Keterangan"],
                [22, 16, 14, 44])

    total = ctx["counts"]["total"] or 1
    rows = [
        ("Open", ctx["counts"]["open"], "Belum ditangani"),
        ("Outstanding", ctx["counts"]["outstanding"], "Sedang ditangani / menunggu"),
        ("Close", ctx["counts"]["closed"], "Selesai ditangani"),
    ]
    row_no = 5
    for label, value, note in rows:
        ws.cell(row=row_no, column=1, value=label).font = Font(bold=True, size=10)
        ws.cell(row=row_no, column=2, value=value)
        pct = ws.cell(row=row_no, column=3, value=value / total)
        pct.number_format = "0.0%"
        ws.cell(row=row_no, column=4, value=note)
        for col in range(1, 5):
            cell = ws.cell(row=row_no, column=col)
            cell.border = BORDER
            cell.fill = PatternFill("solid", fgColor=STATUS_FILL[label])
            if col in (2, 3):
                cell.alignment = Alignment(horizontal="center")
        row_no += 1

    ws.cell(row=row_no, column=1, value="TOTAL").font = Font(bold=True, size=10)
    ws.cell(row=row_no, column=2, value=ctx["counts"]["total"]).font = Font(bold=True)
    for col in range(1, 5):
        cell = ws.cell(row=row_no, column=col)
        cell.border = BORDER
        cell.fill = PatternFill("solid", fgColor=NAVY_SOFT)
        if col == 2:
            cell.alignment = Alignment(horizontal="center")

    # Blok tipe tiket
    row_no += 2
    ws.cell(row=row_no, column=1, value="Berdasarkan Tipe").font = Font(bold=True, size=11,
                                                                       color=NAVY)
    row_no += 1
    _header_row(ws, row_no, ["Tipe", "Kode", "Jumlah", ""])
    for label, code, value in [("Problem", "PR", ctx["type_counts"]["problem"]),
                               ("Feature Request", "FR", ctx["type_counts"]["feature"])]:
        row_no += 1
        ws.cell(row=row_no, column=1, value=label)
        ws.cell(row=row_no, column=2, value=code).alignment = Alignment(horizontal="center")
        ws.cell(row=row_no, column=3, value=value).alignment = Alignment(horizontal="center")
        for col in range(1, 4):
            ws.cell(row=row_no, column=col).border = BORDER

    ws.freeze_panes = "A5"
    return ws


def _sheet_detail(wb, ctx):
    ws = wb.create_sheet("Detail Tiket")
    _title_block(ws, "Detail Tiket", ctx["range_label"], 12)

    headers = ["No. Tiket", "Tipe", "Subjek", "Kode Site", "Pelapor", "PIC",
               "Prioritas", "Status", "Waktu Open", "Waktu Close", "Durasi",
               "Alasan Close"]
    _header_row(ws, 4, headers,
                [14, 16, 42, 12, 20, 20, 12, 14, 18, 18, 12, 40])

    for i, ticket in enumerate(ctx["tickets"], start=5):
        opened = timezone.localtime(ticket.opened_at)
        closed = timezone.localtime(ticket.closed_at) if ticket.closed_at else None
        status_label = ticket.get_status_display()

        values = [
            ticket.number,
            ticket.get_ticket_type_display(),
            ticket.subject,
            ticket.site_code,
            ticket.requester_name,
            ticket.assignee.display_name if ticket.assignee else "—",
            ticket.get_priority_display(),
            status_label,
            opened.strftime("%d/%m/%Y %H:%M"),
            closed.strftime("%d/%m/%Y %H:%M") if closed else "—",
            ticket.duration_display,
            ticket.close_reason or "—",
        ]
        for col, value in enumerate(values, start=1):
            cell = ws.cell(row=i, column=col, value=value)
            cell.border = BORDER
            cell.font = Font(size=10)
            cell.alignment = Alignment(vertical="top",
                                       wrap_text=col in (3, 12),
                                       horizontal="center" if col in (2, 4, 7, 8, 11) else "left")
            if col == 8:
                cell.fill = PatternFill("solid",
                                        fgColor=STATUS_FILL.get(status_label, "FFFFFF"))
    ws.auto_filter.ref = f"A4:L{max(4, 4 + len(ctx['tickets']))}"
    return ws


def _sheet_agents(wb, ctx):
    ws = wb.create_sheet("Performa Agent")
    _title_block(ws, "Performa Agent", ctx["range_label"], 6)

    _header_row(ws, 4, ["Agent", "Jabatan", "Open", "Outstanding", "Close",
                        "Rasio Selesai"], [26, 22, 12, 16, 12, 16])

    for i, agent in enumerate(ctx["agents"], start=5):
        values = [agent["name"], agent["position"], agent["open"],
                  agent["outstanding"], agent["closed"]]
        for col, value in enumerate(values, start=1):
            cell = ws.cell(row=i, column=col, value=value)
            cell.border = BORDER
            cell.font = Font(size=10)
            if col >= 3:
                cell.alignment = Alignment(horizontal="center")
        rate = ws.cell(row=i, column=6, value=agent["rate"] / 100)
        rate.number_format = "0%"
        rate.alignment = Alignment(horizontal="center")
        rate.border = BORDER
    return ws


def build_workbook(ctx):
    """Susun workbook dari konteks laporan; kembalikan objek Workbook."""
    wb = Workbook()
    wb.remove(wb.active)

    _sheet_rekap(wb, ctx)
    _sheet_detail(wb, ctx)
    _sheet_agents(wb, ctx)

    wb.properties.title = f"Laporan {ctx['period_label']} — Ticketing NMS"
    wb.properties.creator = ctx.get("author", "Ticketing NMS")
    return wb


def file_name(period, date_range):
    if period == "monthly":
        return f"Laporan_Bulanan_{date_range.start_date.strftime('%Y-%m')}.xlsx"
    if date_range.start_date == date_range.end_date:
        return f"Laporan_Harian_{date_range.start_date.strftime('%Y-%m-%d')}.xlsx"
    return (f"Laporan_{date_range.start_date.strftime('%Y-%m-%d')}_"
            f"{date_range.end_date.strftime('%Y-%m-%d')}.xlsx")
