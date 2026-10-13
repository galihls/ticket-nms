from django.core.management.base import BaseCommand

from apps.tickets.models import Ticket


class Command(BaseCommand):
    help = "Pindahkan tiket Open yang sudah lewat batas waktu ke Outstanding."

    def handle(self, *args, **options):
        moved = Ticket.objects.auto_escalate()
        self.stdout.write(self.style.SUCCESS(f"{moved} tiket dipindahkan ke Outstanding."))
