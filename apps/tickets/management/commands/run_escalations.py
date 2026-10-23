"""
Management command untuk menjalankan eskalasi email tiket 3 Fase secara terjadwal:
- Fase 1 (1 Hari): Lead NSM
- Fase 2 (5 Hari): Project Manager & Engineer
- Fase 3 (2 Minggu / 14 Hari): Direktur

Dijalankan via Cron setiap hari:
    python manage.py run_escalations

Opsi pengujian:
    python manage.py run_escalations --dry-run
    python manage.py run_escalations --test-lead
    python manage.py run_escalations --test-pm
    python manage.py run_escalations --test-director
    python manage.py run_escalations --test-director --smtp
"""

import getpass

from django.conf import settings
from django.core.mail import get_connection
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.tickets.escalation import process_all_escalations, send_escalation_email
from apps.tickets.models import Ticket


class Command(BaseCommand):
    help = "Pindai tiket PR & FR yang berumur >= 1 hari, >= 5 hari, atau >= 2 minggu, lalu kirim email eskalasi."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Simulasikan pengecekan tanpa mengirim email atau mengubah database.",
        )
        parser.add_argument(
            "--test-lead",
            nargs="?",
            const="__latest__",
            help="Kirim tes eskalasi Lead NSM (Fase 1) langsung (opsional: nomor tiket tertentu, mis. 26PR0001).",
        )
        parser.add_argument(
            "--test-pm",
            nargs="?",
            const="__latest__",
            help="Kirim tes eskalasi PM & Engineer (Fase 2) langsung (opsional: nomor tiket tertentu, mis. 26PR0001).",
        )
        parser.add_argument(
            "--test-manager",
            nargs="?",
            const="__latest__",
            help="Alias untuk --test-pm.",
        )
        parser.add_argument(
            "--test-director",
            nargs="?",
            const="__latest__",
            help="Kirim tes eskalasi Direktur (Fase 3) langsung (opsional: nomor tiket tertentu, mis. 26PR0001).",
        )
        parser.add_argument(
            "--smtp",
            action="store_true",
            help="Paksa pengiriman via koneksi SMTP sungguhan ke internet (Office 365).",
        )
        parser.add_argument(
            "--smtp-password",
            type=str,
            default="",
            help="Password akun pengirim SMTP jika tidak disimpan di .env",
        )

    def _get_test_ticket(self, t_num):
        if t_num == "__latest__":
            return Ticket.objects.exclude(status=Ticket.Status.CLOSED).first() or Ticket.objects.first()
        return Ticket.objects.filter(number=t_num).first()

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        now = timezone.now()

        # Sinkronisasi status tiket yang sudah > 60 menit menjadi Outstanding
        try:
            Ticket.objects.auto_escalate()
        except Exception:
            pass

        conn = None
        if options["smtp"]:
            host = getattr(settings, "EMAIL_HOST", "smtp.office365.com") or "smtp.office365.com"
            port = getattr(settings, "EMAIL_PORT", 587) or 587
            user = getattr(settings, "EMAIL_HOST_USER", "") or "helpdesk@initech.co.id"
            pwd = options["smtp_password"] or getattr(settings, "EMAIL_HOST_PASSWORD", "")
            if not pwd and not dry_run:
                pwd = getpass.getpass(f"Masukkan password SMTP untuk {user}: ")

            self.stdout.write(f"Menyiapkan koneksi SMTP {host}:{port} via akun {user}...")
            conn = get_connection(
                backend="django.core.mail.backends.smtp.EmailBackend",
                host=host,
                port=port,
                username=user,
                password=pwd,
                use_tls=True,
            )

        # ── Mode Pengujian Fase 1: Lead NSM ──────────────────────────────────
        if options["test_lead"] is not None:
            ticket = self._get_test_ticket(options["test_lead"])
            if not ticket:
                self.stdout.write(self.style.ERROR("Tidak ada tiket di database yang bisa diuji coba."))
                return

            lead_email = getattr(settings, "ESCALATION_LEAD_EMAIL", "lead.nsm@initech.co.id")
            self.stdout.write(self.style.NOTICE("\n=== PENGIRIMAN UJI COBA ESKALASI LEAD NSM (FASE 1) ==="))
            self.stdout.write(f"Nomor Tiket : {ticket.number}")
            self.stdout.write(f"Subjek      : {ticket.subject}")
            self.stdout.write(f"Status      : {ticket.get_status_display()}")
            self.stdout.write(f"Penerima    : {lead_email}")
            self.stdout.write(f"Link Tiket  : {settings.SITE_BASE_URL.rstrip('/')}{ticket.get_absolute_url()}\n")

            ok = send_escalation_email(ticket, level="lead", dry_run=dry_run, connection=conn)
            if ok:
                self.stdout.write(self.style.SUCCESS(f"✓ BERHASIL! Email eskalasi Lead NSM telah terkirim ke {lead_email}."))
            else:
                self.stdout.write(self.style.ERROR("✗ Gagal mengirim email eskalasi Lead NSM."))
            return

        # ── Mode Pengujian Fase 2: PM & Engineer ─────────────────────────────
        test_pm_val = options["test_pm"] if options["test_pm"] is not None else options["test_manager"]
        if test_pm_val is not None:
            ticket = self._get_test_ticket(test_pm_val)
            if not ticket:
                self.stdout.write(self.style.ERROR("Tidak ada tiket di database yang bisa diuji coba."))
                return

            pm_email = getattr(settings, "ESCALATION_PM_EMAIL", "pm@initech.co.id")
            eng_email = getattr(settings, "ESCALATION_ENGINEER_EMAIL", "engineer@initech.co.id")
            self.stdout.write(self.style.NOTICE("\n=== PENGIRIMAN UJI COBA ESKALASI PM & ENGINEER (FASE 2) ==="))
            self.stdout.write(f"Nomor Tiket : {ticket.number}")
            self.stdout.write(f"Subjek      : {ticket.subject}")
            self.stdout.write(f"Status      : {ticket.get_status_display()}")
            self.stdout.write(f"Penerima 1  : {pm_email}")
            self.stdout.write(f"Penerima 2  : {eng_email}")
            self.stdout.write(f"Link Tiket  : {settings.SITE_BASE_URL.rstrip('/')}{ticket.get_absolute_url()}\n")

            ok = send_escalation_email(ticket, level="pm", dry_run=dry_run, connection=conn)
            if ok:
                self.stdout.write(self.style.SUCCESS(f"✓ BERHASIL! Email eskalasi Fase 2 telah terkirim ke {pm_email} & {eng_email}."))
            else:
                self.stdout.write(self.style.ERROR("✗ Gagal mengirim email eskalasi PM & Engineer."))
            return

        # ── Mode Pengujian Fase 3: Direktur ──────────────────────────────────
        if options["test_director"] is not None:
            ticket = self._get_test_ticket(options["test_director"])
            if not ticket:
                self.stdout.write(self.style.ERROR("Tidak ada tiket di database yang bisa diuji coba."))
                return

            dir_email = getattr(settings, "ESCALATION_DIRECTOR_EMAIL", "galih.angga524@gmail.com")
            self.stdout.write(self.style.NOTICE("\n=== PENGIRIMAN UJI COBA ESKALASI DIREKTUR (FASE 3) ==="))
            self.stdout.write(f"Nomor Tiket : {ticket.number}")
            self.stdout.write(f"Subjek      : {ticket.subject}")
            self.stdout.write(f"Status      : {ticket.get_status_display()}")
            self.stdout.write(f"Penerima    : {dir_email}")
            self.stdout.write(f"Link Tiket  : {settings.SITE_BASE_URL.rstrip('/')}{ticket.get_absolute_url()}\n")

            ok = send_escalation_email(ticket, level="director", dry_run=dry_run, connection=conn)
            if ok:
                self.stdout.write(self.style.SUCCESS(f"✓ BERHASIL! Email eskalasi Direktur telah terkirim ke {dir_email}."))
                self.stdout.write(self.style.NOTICE("Silakan periksa kotak masuk (Inbox/Spam) akun penerima."))
            else:
                self.stdout.write(self.style.ERROR("✗ Gagal mengirim email eskalasi Direktur. Periksa kredensial SMTP."))
            return

        # ── Mode Normal Terjadwal (Cron) ─────────────────────────────────────
        self.stdout.write(self.style.NOTICE(f"=== PROSES ESKALASI TIKET OTOMATIS ({now.strftime('%d/%m/%Y %H:%M:%S')}) ==="))
        if dry_run:
            self.stdout.write(self.style.WARNING("Mode: DRY-RUN (simulasi tanpa kirim email asli)"))

        lead_email = getattr(settings, "ESCALATION_LEAD_EMAIL", "lead.nsm@initech.co.id")
        pm_email = getattr(settings, "ESCALATION_PM_EMAIL", "pm@initech.co.id")
        eng_email = getattr(settings, "ESCALATION_ENGINEER_EMAIL", "engineer@initech.co.id")
        dir_email = getattr(settings, "ESCALATION_DIRECTOR_EMAIL", "galih.angga524@gmail.com")
        base_url = getattr(settings, "SITE_BASE_URL", "http://localhost:8000")

        self.stdout.write(f"Fase 1 (>=1 hari)  : {lead_email}")
        self.stdout.write(f"Fase 2 (>=5 hari)  : {pm_email}, {eng_email}")
        self.stdout.write(f"Fase 3 (>=2 minggu): {dir_email}")
        self.stdout.write(f"Base URL Link Tiket: {base_url}\n")

        results = process_all_escalations(now=now, dry_run=dry_run)

        self.stdout.write("-" * 55)
        self.stdout.write(f"Kandidat Fase 1 Lead (1 hari)        : {results['lead_candidates']}")
        self.stdout.write(f"Terkirim ke Lead NSM                 : {results['lead_sent']}")
        self.stdout.write(f"Kandidat Fase 2 PM & Eng (5 hari)    : {results['pm_candidates']}")
        self.stdout.write(f"Terkirim ke PM & Engineer            : {results['pm_sent']}")
        self.stdout.write(f"Kandidat Fase 3 Direktur (2 minggu)  : {results['director_candidates']}")
        self.stdout.write(f"Terkirim ke Direktur                 : {results['director_sent']}")

        if results["errors"] > 0:
            self.stdout.write(self.style.ERROR(f"Kegagalan Pengiriman                 : {results['errors']}"))
        else:
            self.stdout.write(self.style.SUCCESS("Semua proses eskalasi selesai dengan lancar tanpa error."))
        self.stdout.write("-" * 55)
