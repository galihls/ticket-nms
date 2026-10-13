"""Model tiket gangguan & permintaan fitur."""

from datetime import timedelta

from django.conf import settings
from django.db import models, transaction
from django.urls import reverse
from django.utils import timezone

from apps.core.models import TimeStampedModel


class TicketQuerySet(models.QuerySet):
    def in_range(self, start, end):
        """Tiket yang dibuat atau ditutup pada rentang tanggal (inklusif)."""
        return self.filter(
            models.Q(opened_at__gte=start, opened_at__lte=end) |
            models.Q(closed_at__gte=start, closed_at__lte=end)
        ).distinct()

    def open(self):
        return self.filter(status=Ticket.Status.OPEN)

    def outstanding(self):
        return self.filter(status=Ticket.Status.OUTSTANDING)

    def closed(self):
        return self.filter(status=Ticket.Status.CLOSED)

    def stale_open(self, now=None):
        """Tiket Open yang sudah melewati batas waktu dan harus jadi Outstanding."""
        now = now or timezone.now()
        return self.filter(status=Ticket.Status.OPEN,
                           opened_at__lte=now - Ticket.AUTO_OUTSTANDING_AFTER)

    def high_priority(self, now=None):
        """Tiket yang masuk High Priority: belum ditutup, PR/FR > 5 hari, RC > 2 bulan (60 hari)."""
        now = now or timezone.now()
        five_days_ago = now - timedelta(days=5)
        two_months_ago = now - timedelta(days=60)

        pr_fr_stale = models.Q(
            ticket_type__in=[Ticket.Type.PROBLEM, Ticket.Type.FEATURE],
            opened_at__lte=five_days_ago,
        )
        rc_stale = models.Q(
            ticket_type=Ticket.Type.RELOCATION,
            opened_at__lte=two_months_ago,
        )
        return self.exclude(status=Ticket.Status.CLOSED).filter(pr_fr_stale | rc_stale)

    def auto_escalate(self):
        """Pindahkan tiket Open ke Outstanding jika sudah melewati batas waktu."""
        from apps.core.models import ActivityLog

        moved = 0
        now = timezone.now()

        # Open -> Outstanding (60 menit)
        tickets = list(self.stale_open(now))
        for ticket in tickets:
            ticket.status = Ticket.Status.OUTSTANDING
            ticket.save(update_fields=["status", "updated_at"])
            ActivityLog.record(
                None, ActivityLog.Verb.TICKET_UPDATE,
                target_label=ticket.number, subject=ticket.subject,
                status=ticket.get_status_display(),
                pic=ticket.requester_phone if ticket.requester_phone else "No PIC number",
                reason="Automatic: Open → Outstanding (timeout reached)",
                url=ticket.get_absolute_url(),
            )
            moved += 1

        return moved


class Company(models.Model):
    """Corporate / client entity. Admin can manage companies dynamically."""
    name = models.CharField("name", max_length=120, unique=True)
    code = models.CharField("code", max_length=32, blank=True, help_text="Short code / abbreviation")
    contact_person = models.CharField("contact person", max_length=120, blank=True)
    contact_phone = models.CharField("contact phone", max_length=32, blank=True)
    address = models.TextField("address", blank=True)
    is_active = models.BooleanField("active", default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "company"
        verbose_name_plural = "companies"

    def __str__(self):
        return self.name

    @property
    def ticket_count(self):
        return Ticket.objects.filter(company=self.name).count()


class Ticket(TimeStampedModel):
    """Satu tiket gangguan (Problem), permintaan fitur (Feature Request), atau relokasi (Relocation)."""

    DEFAULT_COMPANIES = [
        "ITID",
        "Mitseri",
        "PT.LION EXPRESS",
        "CHINA CONSTRUCTION INDUSTRIAL & ENGINEERING",
        "PT SURYA FAJAR INDONESIA",
        "PT ANUGERAH PANCA LAKSANA",
        "TS Tech",
        "PT VIRTUS FACILITY SERVICE",
        "INITECH",
        "BADAN PUSAT STATISTIK",
        "Anter Aja",
    ]

    # Aturan waktu (bisa ditimpa lewat settings TICKET_AUTO_OUTSTANDING_MINUTES /
    # TICKET_CLOSED_EDIT_MINUTES)
    AUTO_OUTSTANDING_AFTER = timedelta(
        minutes=getattr(settings, "TICKET_AUTO_OUTSTANDING_MINUTES", 60))
    CLOSED_EDIT_WINDOW = timedelta(
        minutes=getattr(settings, "TICKET_CLOSED_EDIT_MINUTES", 10))

    class Type(models.TextChoices):
        PROBLEM = "PR", "Problem"
        FEATURE = "FR", "Feature Request"
        RELOCATION = "RC", "Relocation"

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        OUTSTANDING = "outstanding", "Outstanding"
        CLOSED = "closed", "Closed"

    class Priority(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"

    class Source(models.TextChoices):
        EMAIL = "email", "Email"
        CHAT = "chat", "Chat"
        NMS = "nms", "Alert Zabbix"

    class ProblemCategory(models.TextChoices):
        """Kategori gangguan — hanya untuk tiket Problem, jadi dasar donat
        Problem di dashboard dan rekap per site di laporan bulanan."""
        POWER = "power", "Power Outage"
        LOS = "los", "Internet LOS"
        OTHER = "other", "Other"

    # Backward compatibility alias
    class CompanyChoices(models.TextChoices):
        ITID = "ITID", "ITID"
        MITSERI = "Mitseri", "Mitseri"
        LION_EXPRESS = "PT.LION EXPRESS", "PT.LION EXPRESS"
        CHINA_CONSTRUCTION = "CHINA CONSTRUCTION INDUSTRIAL & ENGINEERING", "CHINA CONSTRUCTION INDUSTRIAL & ENGINEERING"
        SURYA_FAJAR = "PT SURYA FAJAR INDONESIA", "PT SURYA FAJAR INDONESIA"
        ANUGERAH_PANCA = "PT ANUGERAH PANCA LAKSANA", "PT ANUGERAH PANCA LAKSANA"
        TS_TECH = "TS Tech", "TS Tech"
        VIRTUS = "PT VIRTUS FACILITY SERVICE", "PT VIRTUS FACILITY SERVICE"
        INITECH = "INITECH", "INITECH"
        BPS = "BADAN PUSAT STATISTIK", "BADAN PUSAT STATISTIK"
        ANTER_AJA = "Anter Aja", "Anter Aja"

    number = models.CharField("nomor tiket", max_length=24, unique=True, editable=False)
    ticket_type = models.CharField("tipe", max_length=2, choices=Type.choices,
                                   default=Type.PROBLEM, db_index=True)

    subject = models.CharField("subjek", max_length=255)
    description = models.TextField("deskripsi")
    problem_category = models.CharField("kategori problem", max_length=16, choices=ProblemCategory.choices, blank=True)
    problem_detail = models.CharField("detail kategori", max_length=120, blank=True)

    status = models.CharField("status", max_length=16, choices=Status.choices,
                              default=Status.OPEN, db_index=True)
    priority = models.CharField("level", max_length=16, choices=Priority.choices,
                                default=Priority.MEDIUM, db_index=True)
    source = models.CharField("sumber", max_length=16, choices=Source.choices,
                              default=Source.NMS)

    requester_name = models.CharField("pelapor", max_length=120)
    requester_email = models.EmailField("email pelapor", blank=True)
    requester_phone = models.CharField("nomor telepon", max_length=20)
    company = models.CharField("perusahaan / unit", max_length=120, db_index=True)
    address = models.TextField("alamat", blank=True, help_text="Alamat saat pembuatan tiket relokasi.")
    site_code = models.CharField("kode site", max_length=32, blank=True, db_index=True)

    relocation_action = models.CharField("tindakan relokasi", max_length=32, blank=True,
                                         choices=[("Relokasi", "Relocation"), ("Dismantle", "Dismantle")])
    new_site = models.CharField("site baru", max_length=64, blank=True)
    new_address = models.TextField("alamat baru", blank=True)

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
            self.Priority.HIGH: "badge--danger",
        }.get(self.priority, "badge--neutral")

    @property
    def type_badge(self):
        if self.ticket_type == self.Type.PROBLEM:
            return "badge--danger"
        elif self.ticket_type == self.Type.RELOCATION:
            return "badge--warn"
        return "badge--teal"

    @property
    def is_closed(self):
        return self.status == self.Status.CLOSED

    @property
    def is_high_priority(self):
        """True jika tiket belum closed dan masuk kriteria High Priority (PR/FR > 5 hari, RC > 2 bulan)."""
        if self.is_closed:
            return False
        now = timezone.now()
        if self.ticket_type in (self.Type.PROBLEM, self.Type.FEATURE):
            return self.opened_at <= now - timedelta(days=5)
        elif self.ticket_type == self.Type.RELOCATION:
            return self.opened_at <= now - timedelta(days=60)
        return False

    # ── Kunci tiket closed ──────────────────────────────────────────────────
    # Admin selalu boleh mengubah. Agent hanya boleh mengubah tiket closed
    # selama CLOSED_EDIT_WINDOW sejak ditutup (untuk koreksi salah klik).

    @property
    def edit_deadline(self):
        if not self.is_closed or not self.closed_at:
            return None
        return self.closed_at + self.CLOSED_EDIT_WINDOW

    @property
    def edit_minutes_left(self):
        deadline = self.edit_deadline
        if not deadline:
            return None
        return max(0, int((deadline - timezone.now()).total_seconds() // 60) + 1)

    def can_edit(self, user):
        if not self.is_closed:
            return True
        if user.is_superuser:
            return True
        deadline = self.edit_deadline
        return bool(deadline and timezone.now() <= deadline)

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
            return f"{total}m"
        hours, minutes = divmod(total, 60)
        if hours < 24:
            return f"{hours}h {minutes}m"
        days, hours = divmod(hours, 24)
        return f"{days}d {hours}h"

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
