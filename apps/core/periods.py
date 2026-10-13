"""Filter kalender bersama — dipakai dashboard dan halaman laporan.

Semua angka di dashboard wajib mengikuti rentang tanggal yang dipilih, jadi
resolusi rentang ini sengaja ditaruh di satu tempat supaya tidak ada halaman
yang menghitung rentangnya sendiri dan hasilnya beda.
"""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from django.utils import timezone

PRESETS = [
    ("today", "Today"),
    ("shift_1", "07:30 - 11:30"),
    ("shift_2", "11:30 - 15:30"),
    ("shift_3", "15:30 - 19:30"),
    ("shift_4", "19:30 - 23:00"),
    ("shift_5", "23:00 - 03:00"),
    ("shift_6", "03:00 - 07:30"),
    ("7d", "Last 7 days"),
    ("30d", "Last 30 days"),
    ("this_month", "This Month"),
    ("last_month", "Last Month"),
    ("custom", "Custom"),
]

DEFAULT_PRESET = "30d"


@dataclass(frozen=True)
class DateRange:
    preset: str
    start_date: date
    end_date: date
    start_time: time = time.min
    end_time: time = time.max

    @property
    def start(self):
        """Awal waktu, sadar zona waktu."""
        if isinstance(self.start_date, datetime):
            return timezone.make_aware(self.start_date) if timezone.is_naive(self.start_date) else self.start_date
        return timezone.make_aware(datetime.combine(self.start_date, self.start_time))

    @property
    def end(self):
        """Akhir waktu - inklusif."""
        if isinstance(self.end_date, datetime):
            return timezone.make_aware(self.end_date) if timezone.is_naive(self.end_date) else self.end_date
        return timezone.make_aware(datetime.combine(self.end_date, self.end_time))

    @property
    def days(self):
        d1 = self.start_date.date() if isinstance(self.start_date, datetime) else self.start_date
        d2 = self.end_date.date() if isinstance(self.end_date, datetime) else self.end_date
        return (d2 - d1).days + 1

    @property
    def label(self):
        for key, text in PRESETS:
            if key == self.preset and key != "custom":
                return text
        if self.start_date == self.end_date:
            return self.start_date.strftime("%d/%m/%Y")
        return (f"{self.start_date.strftime('%d/%m/%Y')} – "
                f"{self.end_date.strftime('%d/%m/%Y')}")

    @property
    def previous(self):
        """Rentang sebelumnya dengan panjang sama — untuk hitung selisih."""
        span = timedelta(days=self.days)
        return DateRange("custom", self.start_date - span, self.start_date - timedelta(days=1))


def _parse(value):
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def resolve(request, default=DEFAULT_PRESET):
    """Baca ?preset=, ?from=, ?to= dari query string menjadi DateRange."""
    today = timezone.localdate()
    preset = request.GET.get("preset") or default

    custom_from = _parse(request.GET.get("from"))
    custom_to = _parse(request.GET.get("to"))
    if custom_from or custom_to:
        preset = "custom"

    if preset == "today":
        return DateRange(preset, today, today)
    elif preset == "shift_1":
        return DateRange(preset, today, today, time(7, 30), time(11, 30))
    elif preset == "shift_2":
        return DateRange(preset, today, today, time(11, 30), time(15, 30))
    elif preset == "shift_3":
        return DateRange(preset, today, today, time(15, 30), time(19, 30))
    elif preset == "shift_4":
        return DateRange(preset, today, today, time(19, 30), time(23, 0))
    elif preset == "shift_5":
        # 23:00 to 03:00 next day
        return DateRange(preset, today, today + timedelta(days=1), time(23, 0), time(3, 0))
    elif preset == "shift_6":
        return DateRange(preset, today, today, time(3, 0), time(7, 30))
    elif preset == "7d":
        start, end = today - timedelta(days=6), today
    elif preset == "this_month":
        start, end = today.replace(day=1), today
    elif preset == "last_month":
        first_this = today.replace(day=1)
        end = first_this - timedelta(days=1)
        start = end.replace(day=1)
    elif preset == "custom":
        start = custom_from or today - timedelta(days=29)
        end = custom_to or today
    else:
        preset = "30d"
        start, end = today - timedelta(days=29), today

    if start > end:
        start, end = end, start
    return DateRange(preset, start, end)
