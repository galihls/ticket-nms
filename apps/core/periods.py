"""Filter kalender bersama — dipakai dashboard dan halaman laporan.

Semua angka di dashboard wajib mengikuti rentang tanggal yang dipilih, jadi
resolusi rentang ini sengaja ditaruh di satu tempat supaya tidak ada halaman
yang menghitung rentangnya sendiri dan hasilnya beda.
"""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from django.utils import timezone

PRESETS = [
    ("today", "Hari ini"),
    ("7d", "7 hari terakhir"),
    ("30d", "30 hari terakhir"),
    ("this_month", "Bulan ini"),
    ("last_month", "Bulan lalu"),
    ("custom", "Kustom"),
]

DEFAULT_PRESET = "30d"


@dataclass(frozen=True)
class DateRange:
    preset: str
    start_date: date
    end_date: date

    @property
    def start(self):
        """Awal hari pertama, sadar zona waktu."""
        return timezone.make_aware(datetime.combine(self.start_date, time.min))

    @property
    def end(self):
        """Akhir hari terakhir — inklusif, supaya tiket sore hari ikut terhitung."""
        return timezone.make_aware(datetime.combine(self.end_date, time.max))

    @property
    def days(self):
        return (self.end_date - self.start_date).days + 1

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
        start = end = today
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
