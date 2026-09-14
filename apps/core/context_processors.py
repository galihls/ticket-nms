from django.conf import settings


def app_meta(request):
    """Identitas aplikasi supaya template tidak perlu hardcode nama perusahaan."""
    return {
        "APP_NAME": settings.APP_NAME,
        "COMPANY_NAME": settings.COMPANY_NAME,
        "COMPANY_SHORT": settings.COMPANY_SHORT,
        "APP_VERSION": settings.APP_VERSION,
        "SSO": settings.SSO,
    }


def ui_state(request):
    """Angka yang dipakai lencana navigasi & lonceng notifikasi.

    Hanya dijalankan untuk pengguna yang sudah masuk; halaman login tidak
    perlu menyentuh database untuk ini.
    """
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return {}

    from apps.core.models import Notification
    from apps.tickets.models import Ticket

    return {
        "nav_open_count": Ticket.objects.open().count(),
        "nav_unread_count": Notification.objects.filter(is_read=False).count(),
        "notifications_preview": Notification.objects.all()[:6],
        "is_admin": user.is_superuser or user.is_staff,
    }
