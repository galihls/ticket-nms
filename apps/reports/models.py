"""Jejak ekspor laporan — berguna untuk tahu laporan mana yang sudah ditarik."""

from django.conf import settings
from django.db import models
from django.utils import timezone


class ReportExport(models.Model):
    class Period(models.TextChoices):
        DAILY = "daily", "Harian"
        MONTHLY = "monthly", "Bulanan"

    period = models.CharField("periode", max_length=16, choices=Period.choices)
    date_from = models.DateField("dari tanggal")
    date_to = models.DateField("sampai tanggal")
    file_name = models.CharField("nama berkas", max_length=160)
    row_count = models.PositiveIntegerField("jumlah baris", default=0)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="report_exports",
    )
    created_at = models.DateTimeField("waktu", default=timezone.now, db_index=True)

    class Meta:
        verbose_name = "ekspor laporan"
        verbose_name_plural = "ekspor laporan"
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return self.file_name
