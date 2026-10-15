"""Model dasar yang diwarisi app lain + jejak aktivitas dan notifikasi."""

from django.conf import settings
from django.db import models
from django.utils import timezone


class TimeStampedModel(models.Model):
    """Menambahkan jejak waktu pembuatan dan perubahan."""

    created_at = models.DateTimeField("dibuat pada", auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField("diubah pada", auto_now=True)

    class Meta:
        abstract = True


class BaseModel(TimeStampedModel):
    """TimeStampedModel + jejak siapa yang membuat/mengubah.

    Field pelaku diisi di layer view/form, bukan otomatis, supaya perintah
    manajemen dan proses sinkronisasi tetap bisa menyimpan tanpa user.
    """

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="dibuat oleh",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="%(app_label)s_%(class)s_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="diubah oleh",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="%(app_label)s_%(class)s_updated",
    )

    class Meta:
        abstract = True


class ActivityLog(models.Model):
    """Audit trail — siapa melakukan apa, kapan.

    Sengaja memakai kolom datar (bukan GenericForeignKey) supaya baris log
    tetap terbaca walau objek aslinya sudah dihapus. Untuk halaman audit,
    teks yang tersimpan lebih berguna daripada relasi yang bisa putus.
    """

    class Verb(models.TextChoices):
        TICKET_CREATE = "ticket_create", "Created ticket"
        TICKET_UPDATE = "ticket_update", "Updated ticket"
        TICKET_REPLY = "ticket_reply", "Replied to ticket"
        TICKET_NOTE = "ticket_note", "Added internal note"
        TICKET_CLOSE = "ticket_close", "Closed ticket"
        TICKET_REOPEN = "ticket_reopen", "Reopened ticket"
        TICKET_DELETE = "ticket_delete", "Deleted ticket"
        ARTICLE_CREATE = "article_create", "Created solution article"
        REPORT_EXPORT = "report_export", "Exported report"
        LOGIN = "login", "Signed in"

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="pelaku",
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name="activities",
    )
    actor_label = models.CharField("nama pelaku", max_length=120, blank=True)
    verb = models.CharField("aksi", max_length=32, choices=Verb.choices, db_index=True)

    # Ringkasan objek — disimpan sebagai teks, tahan walau objeknya dihapus
    target_label = models.CharField("objek", max_length=64, blank=True)
    subject = models.CharField("subjek", max_length=255, blank=True)
    status = models.CharField("status", max_length=32, blank=True)
    pic = models.CharField("person in charge", max_length=120, blank=True)
    reason = models.TextField("alasan / keterangan", blank=True)
    url = models.CharField("tautan", max_length=255, blank=True)

    created_at = models.DateTimeField("waktu", default=timezone.now, db_index=True)

    class Meta:
        verbose_name = "log aktivitas"
        verbose_name_plural = "log aktivitas"
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"{self.actor_label} — {self.get_verb_display()} {self.target_label}"

    @property
    def badge_class(self):
        return {
            self.Verb.TICKET_CREATE: "badge--info",
            self.Verb.TICKET_UPDATE: "badge--neutral",
            self.Verb.TICKET_REPLY: "badge--teal",
            self.Verb.TICKET_NOTE: "badge--neutral",
            self.Verb.TICKET_CLOSE: "badge--ok",
            self.Verb.TICKET_REOPEN: "badge--warn",
            self.Verb.ARTICLE_CREATE: "badge--teal",
            self.Verb.REPORT_EXPORT: "badge--neutral",
            self.Verb.LOGIN: "badge--neutral",
        }.get(self.verb, "badge--neutral")

    @classmethod
    def record(cls, actor, verb, **fields):
        """Jalan pintas supaya view tidak perlu mengisi actor_label manual."""
        return cls.objects.create(
            actor=actor if actor and actor.is_authenticated else None,
            actor_label=getattr(actor, "display_name", "") or "System",
            verb=verb,
            **fields,
        )


class Notification(models.Model):
    """Notifikasi global — admin melihat aktivitas tiket dari seluruh agent."""

    class Level(models.TextChoices):
        INFO = "info", "Information"
        SUCCESS = "success", "Success"
        WARNING = "warning", "Warning"
        DANGER = "danger", "Urgent"

    title = models.CharField("judul", max_length=160)
    body = models.CharField("isi", max_length=255, blank=True)
    url = models.CharField("tautan", max_length=255, blank=True)
    level = models.CharField("tingkat", max_length=16, choices=Level.choices,
                             default=Level.INFO)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="notifications_sent",
    )
    is_read = models.BooleanField("sudah dibaca", default=False, db_index=True)
    created_at = models.DateTimeField("waktu", default=timezone.now, db_index=True)

    class Meta:
        verbose_name = "notifikasi"
        verbose_name_plural = "notifikasi"
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return self.title

    @property
    def dot_color(self):
        return {
            self.Level.INFO: "#175CD3",
            self.Level.SUCCESS: "#067647",
            self.Level.WARNING: "#DC6803",
            self.Level.DANGER: "#B42318",
        }.get(self.level, "#667085")

    @property
    def badge_class(self):
        return {
            self.Level.INFO: "badge--info",
            self.Level.SUCCESS: "badge--ok",
            self.Level.WARNING: "badge--warn",
            self.Level.DANGER: "badge--danger",
        }.get(self.level, "badge--neutral")
