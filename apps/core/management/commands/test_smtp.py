"""
Management command to test SMTP connectivity and send a trial email via Microsoft 365.
Usage:
    python manage.py test_smtp
    python manage.py test_smtp --user helpdesk@initech.co.id --to myemail@initech.co.id
"""

import getpass
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Test SMTP email delivery to Microsoft 365 / corporate mail server."

    def add_arguments(self, parser):
        parser.add_argument(
            "--user",
            type=str,
            default="",
            help="SMTP sender address (e.g. helpdesk@initech.co.id)",
        )
        parser.add_argument(
            "--password",
            type=str,
            default="",
            help="SMTP password (optional, will prompt securely if omitted)",
        )
        parser.add_argument(
            "--to",
            type=str,
            default="",
            help="Recipient email address to receive the test message",
        )
        parser.add_argument(
            "--host",
            type=str,
            default="smtp.office365.com",
            help="SMTP Host (default: smtp.office365.com)",
        )
        parser.add_argument(
            "--port",
            type=int,
            default=587,
            help="SMTP Port (default: 587)",
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("=== TEST PENGIRIMAN EMAIL SMTP MICROSOFT 365 ==="))

        host = options["host"]
        port = options["port"]

        user = options["user"].strip()
        if not user:
            # Check settings / env first
            user = getattr(settings, "EMAIL_HOST_USER", "") or "helpdesk@initech.co.id"
            prompt_user = input(f"Alamat email pengirim [{user}]: ").strip()
            if prompt_user:
                user = prompt_user

        password = options["password"]
        if not password:
            # Check settings / env first
            password = getattr(settings, "EMAIL_HOST_PASSWORD", "")
            if not password:
                password = getpass.getpass(f"Masukkan password untuk {user}: ")

        to_email = options["to"].strip()
        if not to_email:
            to_email = input(f"Kirim email tes ke alamat [{user}]: ").strip() or user

        self.stdout.write(f"\n[1/4] Menghubungkan ke server {host}:{port}...")
        try:
            server = smtplib.SMTP(host, port, timeout=20)
            server.ehlo()
            self.stdout.write(self.style.SUCCESS("  ✓ Berhasil terhubung ke host SMTP."))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"  ✗ Gagal terhubung ke host: {e}"))
            return

        self.stdout.write("[2/4] Mengaktifkan enkripsi TLS (STARTTLS)...")
        try:
            server.starttls()
            server.ehlo()
            self.stdout.write(self.style.SUCCESS("  ✓ Enkripsi TLS aktif."))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"  ✗ Gagal mengaktifkan TLS: {e}"))
            server.quit()
            return

        self.stdout.write(f"[3/4] Melakukan login otentikasi sebagai {user}...")
        try:
            server.login(user, password)
            self.stdout.write(self.style.SUCCESS("  ✓ Login otentikasi BERHASIL! Server menerima kredensial."))
        except smtplib.SMTPAuthenticationError as auth_err:
            self.stdout.write(self.style.ERROR(f"  ✗ Gagal login (Authentication Error): {auth_err}"))
            self.stdout.write(
                self.style.WARNING(
                    "\nPenjelasan kemungkinan penyebab:\n"
                    "1. Password salah / baru diubah.\n"
                    "2. Akun menggunakan MFA (Verifikasi 2 Langkah). Solusi: buat 'App Password'.\n"
                    "3. Fitur 'Authenticated SMTP' belum diaktifkan oleh admin IT di M365 tenant."
                )
            )
            server.quit()
            return
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"  ✗ Terjadi kesalahan: {e}"))
            server.quit()
            return

        self.stdout.write(f"[4/4] Mengirim email uji coba ke {to_email}...")
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = "Uji Coba Pengiriman Email — Ticketing NMS INITECH"
            msg["From"] = f"Ticketing NMS <{user}>"
            msg["To"] = to_email

            text_body = (
                "Halo!\n\n"
                "Ini adalah email uji coba dari sistem Ticketing NMS PT Ideologi Nusa Integrasi (INITECH).\n"
                "Koneksi SMTP Microsoft 365 telah berfungsi dengan sempurna.\n\n"
                "— Sistem Ticketing NMS"
            )
            html_body = f"""
            <!DOCTYPE html>
            <html>
            <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; margin: 0; padding: 24px; background: #f4f6f8;">
              <div style="max-width: 560px; margin: 0 auto; background: #ffffff; border-radius: 8px; border: 1px solid #e1e4ea; overflow: hidden;">
                <div style="background: #16294F; padding: 20px 24px;">
                  <h2 style="color: #ffffff; margin: 0; font-size: 18px; font-weight: 600;">Ticketing NMS — INITECH</h2>
                  <p style="color: #35C4BC; margin: 4px 0 0; font-size: 13px;">Uji Coba Pengiriman Notifikasi Email</p>
                </div>
                <div style="padding: 24px;">
                  <div style="background: #E7F6EE; border-left: 4px solid #067647; padding: 12px 16px; border-radius: 4px; margin-bottom: 20px;">
                    <strong style="color: #067647;">✓ Koneksi Berhasil!</strong>
                    <p style="margin: 4px 0 0; font-size: 13px; color: #067647;">Koneksi SMTP Microsoft 365 via akun <strong>{user}</strong> telah berhasil dikonfigurasi.</p>
                  </div>
                  <p style="color: #344054; font-size: 14px; line-height: 1.6;">
                    Email ini dikirim langsung dari aplikasi lokal Ticketing NMS untuk memastikan saluran eskalasi notifikasi ke atasan dan direktur siap digunakan.
                  </p>
                  <hr style="border: none; border-top: 1px solid #eef2f6; margin: 20px 0;">
                  <p style="color: #667085; font-size: 12px; margin: 0;">
                    Dikirim oleh <strong>Ticketing NMS</strong> · PT Ideologi Nusa Integrasi
                  </p>
                </div>
              </div>
            </body>
            </html>
            """
            msg.attach(MIMEText(text_body, "plain"))
            msg.attach(MIMEText(html_body, "html"))

            server.sendmail(user, [to_email], msg.as_string())
            server.quit()
            self.stdout.write(self.style.SUCCESS(f"\n SELAMAT! Email uji coba BERHASIL terkirim ke {to_email}!"))
            self.stdout.write(self.style.NOTICE("Silakan periksa kotak masuk (Inbox/Spam) email penerima sekarang.\n"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"  ✗ Gagal mengirim email: {e}"))
