"""Jejak ekspor laporan — berguna untuk tahu laporan mana yang sudah ditarik."""

from django.conf import settings
from django.db import models
from django.utils import timezone


class ReportExport(models.Model):
    class Period(models.TextChoices):
        DAILY = "daily", "Daily"
        MONTHLY = "monthly", "Monthly"

    period = models.CharField("period", max_length=16, choices=Period.choices)
    date_from = models.DateField("from date")
    date_to = models.DateField("to date")
    file_name = models.CharField("file name", max_length=160)
    row_count = models.PositiveIntegerField("row count", default=0)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="report_exports",
    )
    created_at = models.DateTimeField("created at", default=timezone.now, db_index=True)

    class Meta:
        verbose_name = "report export"
        verbose_name_plural = "report exports"
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return self.file_name
