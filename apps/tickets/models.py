"""Model tiket gangguan & permintaan fitur."""

from django.conf import settings
from django.db import models, transaction
from django.urls import reverse
from django.utils import timezone

from apps.core.models import TimeStampedModel


class TicketQuerySet(models.QuerySet):
    def in_range(self, start, end):
        """Tiket yang dibuat pada rentang tanggal dashboard (inklusif)."""
        return self.filter(opened_at__gte=start, opened_at__lte=end)

    def open(self):
        return self.filter(status=Ticket.Status.OPEN)

    def outstanding(self):
        return self.filter(status=Ticket.Status.OUTSTANDING)

    def closed(self):
        return self.filter(status=Ticket.Status.CLOSED)


class Ticket(TimeStampedModel):
    """Satu tiket gangguan (Problem) atau permintaan fitur (Feature Request)."""

    class Type(models.TextChoices):
        PROBLEM = "PR", "Problem"
        FEATURE = "FR", "Feature Request"

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        OUTSTANDING = "outstanding", "Outstanding"
        CLOSED = "closed", "Close"

    class Priority(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"
        URGENT = "urgent", "Urgent"

    class Source(models.TextChoices):
        PORTAL = "portal", "Portal"
        EMAIL = "email", "Email"
        PHONE = "phone", "Telepon"
        CHAT = "chat", "Chat"
        NMS = "nms", "Alert NMS"

    number = models.CharField("nomor tiket", max_length=24, unique=True, editable=False)
    ticket_type = models.CharField("tipe", max_length=2, choices=Type.choices,
                                   default=Type.PROBLEM, db_index=True)

    subject = models.CharField("subjek", max_length=255)
    description = models.TextField("deskripsi", blank=True)

    status = models.CharField("status", max_length=16, choices=Status.choices,
                              default=Status.OPEN, db_index=True)
    priority = models.CharField("prioritas", max_length=16, choices=Priority.choices,
                                default=Priority.MEDIUM, db_index=True)
    source = models.CharField("sumber", max_length=16, choices=Source.choices,
                              default=Source.PORTAL)

    requester_name = models.CharField("pelapor", max_length=120)
    requester_email = models.EmailField("email pelapor", blank=True)
    company = models.CharField("perusahaan / unit", max_length=120, blank=True)
    site_code = models.CharField("kode site", max_length=32, blank=True, db_index=True)

    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="person in charge",
        on_delete=models.SET_NULL, null=True, blank=True, related_name="tickets_assigned",
    )
    group = models.CharField("grup penanganan", max_length=64, blank=True)

    opened_at = models.DateTimeField("waktu open", default=timezone.now, db_index=True)
    due_at = models.DateTimeField("target selesai", null=True, blank=True)
    first_response_at = models.DateTimeField("respons pertama", null=True, blank=True)
    closed_at = models.DateTimeField("waktu close", null=True, blank=True)
    close_reason = models.TextField("alasan close", blank=True)

    tags = models.CharField("tag", max_length=180, blank=True,
                            help_text="Pisahkan dengan koma.")

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="dibuat oleh",
        on_delete=models.SET_NULL, null=True, blank=True, related_name="tickets_created",
    )

    objects = TicketQuerySet.as_manager()

    class Meta:
        verbose_name = "tiket"
        verbose_name_plural = "tiket"
        ordering = ["-opened_at", "-id"]
        indexes = [models.Index(fields=["status", "opened_at"])]

    def __str__(self):
        return f"{self.number} — {self.subject}"

    def get_absolute_url(self):
        return reverse("tickets:detail", args=[self.number])

    # ── Penomoran otomatis: [Tahun 2 digit][Kode tipe][Nomor urut] ──────────
    # Contoh: 26PR0001, 26FR0042. Urutan berjalan per tahun + per tipe.

    @classmethod
    def next_number(cls, ticket_type, when=None):
        when = when or timezone.localtime()
        prefix = f"{when.year % 100:02d}{ticket_type}"
        last = (
            cls.objects.filter(number__startswith=prefix)
            .order_by("-number")
            .values_list("number", flat=True)
            .first()
        )
        seq = int(last[len(prefix):]) + 1 if last else 1
        # Minimal 4 digit, tetapi tidak dipotong kalau sudah lewat 9999
        return f"{prefix}{seq:04d}"

    def save(self, *args, **kwargs):
        if not self.number:
            with transaction.atomic():
                self.number = self.next_number(self.ticket_type, self.opened_at)
                return super().save(*args, **kwargs)
        return super().save(*args, **kwargs)

    # ── Turunan untuk tampilan ─────────────────────────────────────────────

    @property
    def status_badge(self):
        return {
            self.Status.OPEN: "badge--info",
            self.Status.OUTSTANDING: "badge--warn",
            self.Status.CLOSED: "badge--ok",
        }[self.status]

    @property
    def priority_badge(self):
        return {
            self.Priority.LOW: "badge--neutral",
            self.Priority.MEDIUM: "badge--info",
            self.Priority.HIGH: "badge--high",
            self.Priority.URGENT: "badge--danger",
        }[self.priority]

    @property
    def type_badge(self):
        return "badge--danger" if self.ticket_type == self.Type.PROBLEM else "badge--teal"

    @property
    def is_closed(self):
        return self.status == self.Status.CLOSED

    @property
    def is_overdue(self):
        return bool(self.due_at and not self.is_closed and self.due_at < timezone.now())

    @property
    def duration_minutes(self):
        end = self.closed_at or timezone.now()
        return int((end - self.opened_at).total_seconds() // 60)

    @property
    def duration_display(self):
        total = self.duration_minutes
        if total < 60:
            return f"{total} mnt"
        hours, minutes = divmod(total, 60)
        if hours < 24:
            return f"{hours}j {minutes}m"
        days, hours = divmod(hours, 24)
        return f"{days}h {hours}j"

    @property
    def tag_list(self):
        return [t.strip() for t in self.tags.split(",") if t.strip()]


class TicketReply(TimeStampedModel):
    """Percakapan pada tiket — balasan ke pelapor atau catatan internal."""

    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="replies")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="ticket_replies",
    )
    author_label = models.CharField("nama penulis", max_length=120, blank=True)
    body = models.TextField("isi")
    is_private = models.BooleanField(
        "catatan internal", default=False,
        help_text="Catatan internal tidak terlihat oleh pelapor.",
    )

    class Meta:
        verbose_name = "balasan tiket"
        verbose_name_plural = "balasan tiket"
        ordering = ["created_at", "id"]

    def __str__(self):
        return f"{self.ticket.number} · {self.author_label}"

    @property
    def initials(self):
        parts = [p for p in self.author_label.split() if p]
        return "".join(p[0] for p in parts[:2]).upper() or "??"
