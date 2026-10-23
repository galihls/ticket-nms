"""Setelan lingkungan produksi."""

from .base import *  # noqa: F403
from .base import env

DEBUG = False

# Wajib di-set lewat environment, tidak boleh pakai default.
SECRET_KEY = env("DJANGO_SECRET_KEY")
ALLOWED_HOSTS = env("DJANGO_ALLOWED_HOSTS")
CSRF_TRUSTED_ORIGINS = env.list("DJANGO_CSRF_TRUSTED_ORIGINS", default=[])

# ── Keamanan ──────────────────────────────────────────────────────────────
# Jika diakses via HTTP murni (IP address), DJANGO_SECURE_SSL_REDIRECT=False
SECURE_SSL_REDIRECT = env.bool("DJANGO_SECURE_SSL_REDIRECT", default=False)
SESSION_COOKIE_SECURE = env.bool("DJANGO_SESSION_COOKIE_SECURE", default=SECURE_SSL_REDIRECT)
CSRF_COOKIE_SECURE = env.bool("DJANGO_CSRF_COOKIE_SECURE", default=SECURE_SSL_REDIRECT)
SESSION_COOKIE_HTTPONLY = True

if SECURE_SSL_REDIRECT:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
else:
    SECURE_HSTS_SECONDS = 0

SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

# ── Email ─────────────────────────────────────────────────────────────────
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = env("EMAIL_HOST", default="")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="noreply@initech.co.id")
SITE_BASE_URL = env("SITE_BASE_URL", default="http://20.199.199.201")

# ── Logging ───────────────────────────────────────────────────────────────
LOGS_DIR = BASE_DIR / "logs"  # noqa: F405
LOGS_DIR.mkdir(exist_ok=True)

# Simpan log ke file juga, bukan hanya console.
LOGGING["handlers"]["file"] = {  # noqa: F405
    "class": "logging.handlers.RotatingFileHandler",
    "filename": LOGS_DIR / "app.log",
    "maxBytes": 10 * 1024 * 1024,
    "backupCount": 10,
    "formatter": "verbose",
}
LOGGING["root"]["handlers"] = ["console", "file"]  # noqa: F405
LOGGING["loggers"]["apps"]["handlers"] = ["console", "file"]  # noqa: F405

# ── Single Sign-On Office 365 ─────────────────────────────────────────────
# Di produksi, matikan bypass demo akun agar tidak otomatis login sebagai admin.
# Tombol disembunyikan sampai integrasi Azure AD sesungguhnya dikonfigurasi.
SSO["DEMO_MODE"] = env.bool("SSO_DEMO_MODE", default=False)  # noqa: F405
SSO["ENABLED"] = env.bool("SSO_ENABLED", default=False)  # noqa: F405

