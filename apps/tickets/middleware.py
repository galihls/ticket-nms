"""Eskalasi otomatis Open → Outstanding tanpa perlu Celery/cron.

Setiap request (dibatasi paling sering sekali per ESCALATE_EVERY detik)
memeriksa tiket Open yang sudah melewati Ticket.AUTO_OUTSTANDING_AFTER dan
memindahkannya ke Outstanding. Dijalankan *sebelum* view, jadi dashboard dan
daftar tiket selalu menampilkan status yang sudah benar.

Untuk produksi tetap disarankan menjadwalkan `manage.py escalate_tickets`
(cron / Task Scheduler) agar eskalasi jalan walau tidak ada yang membuka web.
"""

import logging
import time

logger = logging.getLogger(__name__)

ESCALATE_EVERY = 60  # detik
_last_run = 0.0


class AutoEscalateMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        global _last_run
        now = time.monotonic()
        if now - _last_run >= ESCALATE_EVERY:
            _last_run = now
            try:
                from .models import Ticket
                moved = Ticket.objects.auto_escalate()
                if moved:
                    logger.info("Auto-escalated %s ticket(s) to Outstanding or High Priority", moved)
            except Exception:  # jangan sampai eskalasi menjatuhkan request
                logger.exception("Auto-escalation failed")
        return self.get_response(request)
