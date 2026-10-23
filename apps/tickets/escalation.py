"""
Layanan eskalasi tiket otomatis via email 3 Fase:
- Fase 1 (1 Hari): Lead NSM
- Fase 2 (5 Hari): Project Manager & Engineer
- Fase 3 (2 Minggu / 14 Hari): Direktur

Aturan bisnis:
- Hanya berlaku untuk tiket bertipe Problem (PR) dan Feature Request (FR).
- Tiket yang sudah Closed tidak akan dieskalasi.
- Status tiket selalu dinamis mengikuti status terkini di sistem.
- Setiap fase eskalasi HANYA dikirimkan tepat 1 kali per tiket (anti-spam berbasis flag database).
"""

from datetime import timedelta
import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone

from apps.core.models import ActivityLog, Notification
from .models import Ticket

logger = logging.getLogger(__name__)


def _normalize_recipients(recipients):
    """Bantu normalisasi alamat email menjadi list of valid string."""
    if not recipients:
        return []
    if isinstance(recipients, str):
        candidates = [r.strip() for r in recipients.split(",") if r.strip()]
    elif isinstance(recipients, (list, tuple, set)):
        candidates = [str(r).strip() for r in recipients if r and str(r).strip()]
    else:
        candidates = [str(recipients).strip()]

    # Unik tanpa merusak urutan
    seen = set()
    cleaned = []
    for c in candidates:
        if c.lower() not in seen:
            seen.add(c.lower())
            cleaned.append(c)
    return cleaned


def send_escalation_email(ticket, level="lead", recipients=None, dry_run=False, connection=None):
    """
    Kirim email eskalasi untuk satu tiket.
    level:
      - "lead": Fase 1 (>= 1 Hari) -> Lead NSM
      - "pm" (atau "manager"): Fase 2 (>= 5 Hari) -> PM & Engineer
      - "director": Fase 3 (>= 2 Minggu / 14 Hari) -> Direktur
    """
    now = timezone.now()
    base_url = getattr(settings, "SITE_BASE_URL", "http://localhost:8000").rstrip("/")
    ticket_url = f"{base_url}{ticket.get_absolute_url()}"
    opened_local = timezone.localtime(ticket.opened_at)

    ctx = {
        "ticket": ticket,
        "ticket_url": ticket_url,
        "opened_formatted": opened_local.strftime("%d/%m/%Y %H:%M"),
        "duration_display": ticket.duration_display,
        "app_name": getattr(settings, "APP_NAME", "Ticketing NMS"),
        "company_name": getattr(settings, "COMPANY_NAME", "PT Ideologi Nusa Integrasi"),
        "company_short": getattr(settings, "COMPANY_SHORT", "INITECH"),
    }

    if level == "director":
        template_name = "emails/escalation_director.html"
        subject = f"[ESKALASI 2 MINGGU] Tiket {ticket.number}: {ticket.subject} — Belum Terselesaikan"
        default_recipients = [
            getattr(settings, "ESCALATION_DIRECTOR_EMAIL", "galih.angga524@gmail.com")
        ]
        log_label = "Fase 3 (>2 minggu)"
        notif_title = f"Eskalasi 2 Minggu: {ticket.number}"
        notif_level = Notification.Level.DANGER
        field_to_update = "escalated_to_director_at"

    elif level in ("pm", "manager"):
        level = "pm"
        template_name = "emails/escalation_pm_engineer.html"
        subject = f"[ESKALASI 5 HARI] Tiket {ticket.number}: {ticket.subject} — Perlu Perhatian PM & Engineer"
        default_recipients = [
            getattr(settings, "ESCALATION_PM_EMAIL", "pm@initech.co.id"),
            getattr(settings, "ESCALATION_ENGINEER_EMAIL", "engineer@initech.co.id"),
        ]
        log_label = "Fase 2 (5 hari)"
        notif_title = f"Eskalasi 5 Hari: {ticket.number}"
        notif_level = Notification.Level.WARNING
        field_to_update = "escalated_to_pm_at"

    else:  # lead / fase 1
        level = "lead"
        template_name = "emails/escalation_lead.html"
        subject = f"[ESKALASI 1 HARI] Tiket {ticket.number}: {ticket.subject} — Perhatian Lead NSM"
        default_recipients = [
            getattr(settings, "ESCALATION_LEAD_EMAIL", "lead.nsm@initech.co.id")
        ]
        log_label = "Fase 1 (1 hari)"
        notif_title = f"Eskalasi 1 Hari: {ticket.number}"
        notif_level = Notification.Level.INFO
        field_to_update = "escalated_to_lead_at"

    to_emails = _normalize_recipients(recipients) if recipients else _normalize_recipients(default_recipients)
    if not to_emails:
        logger.warning("No recipients configured for escalation %s on ticket %s", level, ticket.number)
        return False

    dest_str = ", ".join(to_emails)
    log_reason = f"Eskalasi {log_label}: Email eskalasi terkirim ke {dest_str}"
    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@initech.co.id")

    if dry_run:
        logger.info("[DRY-RUN] Would send %s escalation for %s to %s", level, ticket.number, dest_str)
        return True

    try:
        html_content = render_to_string(template_name, ctx)
        text_content = (
            f"{subject}\n\n"
            f"Nomor Tiket: {ticket.number}\n"
            f"Tipe: {ticket.get_ticket_type_display()}\n"
            f"Subjek: {ticket.subject}\n"
            f"Perusahaan: {ticket.company or '—'}\n"
            f"Status: {ticket.get_status_display()}\n"
            f"Waktu Buka: {ctx['opened_formatted']} WIB\n"
            f"Durasi: {ticket.duration_display}\n\n"
            f"Buka tiket di: {ticket_url}\n\n"
            f"— {ctx['company_name']}"
        )

        msg = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=from_email,
            to=to_emails,
            connection=connection,
        )
        msg.attach_alternative(html_content, "text/html")
        msg.send(fail_silently=False)

        # Update penanda tanggal pada tiket
        setattr(ticket, field_to_update, now)
        ticket.save(update_fields=[field_to_update])

        # Catat jejak audit trail
        ActivityLog.record(
            None,
            ActivityLog.Verb.TICKET_UPDATE,
            target_label=ticket.number,
            subject=ticket.subject,
            status=ticket.get_status_display(),
            pic=ticket.assignee.display_name if ticket.assignee else "Unassigned",
            reason=log_reason,
            url=ticket.get_absolute_url(),
        )

        # Buat notifikasi internal sistem
        Notification.objects.create(
            title=notif_title,
            body=f"{ticket.subject[:70]} · Email terkirim ke {dest_str}",
            url=ticket.get_absolute_url(),
            actor=ticket.assignee,
            level=notif_level,
        )

        logger.info("Sent %s escalation for ticket %s to %s", level, ticket.number, dest_str)
        return True

    except Exception as exc:
        logger.exception("Failed to send %s escalation for ticket %s to %s: %s", level, ticket.number, dest_str, exc)
        return False


def process_all_escalations(now=None, dry_run=False):
    """
    Pindai seluruh tiket PR & FR yang memenuhi syarat 3 fase eskalasi:
    1. Fase 1: >= 1 Hari  -> Lead NSM
    2. Fase 2: >= 5 Hari  -> PM & Engineer
    3. Fase 3: >= 14 Hari -> Direktur

    Mengembalikan dict rekap hasil eksekusi.
    """
    now = now or timezone.now()
    one_day_ago = now - timedelta(days=1)
    five_days_ago = now - timedelta(days=5)
    two_weeks_ago = now - timedelta(days=14)

    target_types = [Ticket.Type.PROBLEM, Ticket.Type.FEATURE]
    base_qs = Ticket.objects.exclude(status=Ticket.Status.CLOSED).filter(ticket_type__in=target_types)

    # 1. Fase 1: Umur >= 1 Hari (belum pernah eskalasi lead)
    lead_candidates = (
        base_qs.filter(
            opened_at__lte=one_day_ago,
            escalated_to_lead_at__isnull=True,
        )
        .select_related("assignee")
    )

    # 2. Fase 2: Umur >= 5 Hari (belum pernah eskalasi pm)
    pm_candidates = (
        base_qs.filter(
            opened_at__lte=five_days_ago,
            escalated_to_pm_at__isnull=True,
        )
        .select_related("assignee")
    )

    # 3. Fase 3: Umur >= 2 Minggu / 14 Hari (belum pernah eskalasi direktur)
    director_candidates = (
        base_qs.filter(
            opened_at__lte=two_weeks_ago,
            escalated_to_director_at__isnull=True,
        )
        .select_related("assignee")
    )

    results = {
        "lead_candidates": lead_candidates.count(),
        "pm_candidates": pm_candidates.count(),
        "director_candidates": director_candidates.count(),
        "lead_sent": 0,
        "pm_sent": 0,
        "director_sent": 0,
        "errors": 0,
    }

    # Proses kirim email Fase 1 (Lead NSM)
    for ticket in lead_candidates:
        success = send_escalation_email(ticket, level="lead", dry_run=dry_run)
        if success:
            results["lead_sent"] += 1
        else:
            results["errors"] += 1

    # Proses kirim email Fase 2 (PM & Engineer)
    for ticket in pm_candidates:
        success = send_escalation_email(ticket, level="pm", dry_run=dry_run)
        if success:
            results["pm_sent"] += 1
        else:
            results["errors"] += 1

    # Proses kirim email Fase 3 (Direktur)
    for ticket in director_candidates:
        success = send_escalation_email(ticket, level="director", dry_run=dry_run)
        if success:
            results["director_sent"] += 1
        else:
            results["errors"] += 1

    return results
