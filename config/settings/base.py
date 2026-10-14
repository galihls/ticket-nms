"""
Setelan dasar Ticketing NMS.

Dipakai bersama oleh dev.py dan prod.py. Semua nilai yang berbeda antar
lingkungan diambil dari environment variable (lihat .env.example).
"""

from pathlib import Path

import environ

# BASE_DIR = root repo (tempat manage.py berada)
BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env(
    DJANGO_DEBUG=(bool, False),
    DJANGO_ALLOWED_HOSTS=(list, ["localhost", "127.0.0.1"]),
    DATABASE_URL=(str, f"sqlite:///{BASE_DIR / 'db.sqlite3'}"),
    ZABBIX_URL=(str, ""),
    ZABBIX_API_TOKEN=(str, ""),
    ZABBIX_USERNAME=(str, ""),
    ZABBIX_PASSWORD=(str, ""),
    ZABBIX_VERIFY_SSL=(bool, True),
    ZABBIX_TIMEOUT=(int, 30),
)

# Baca .env kalau ada (di produksi boleh pakai env var asli tanpa file)
env_file = BASE_DIR / ".env"
if env_file.exists():
    environ.Env.read_env(env_file)

SECRET_KEY = env("DJANGO_SECRET_KEY", default="dev-only-insecure-key-ganti-di-produksi")
DEBUG = env("DJANGO_DEBUG")
ALLOWED_HOSTS = env("DJANGO_ALLOWED_HOSTS")
CSRF_TRUSTED_ORIGINS = env.list("DJANGO_CSRF_TRUSTED_ORIGINS", default=[])


# ── Aplikasi ──────────────────────────────────────────────────────────────

DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.humanize",
    "django.contrib.staticfiles",
]

LOCAL_APPS = [
    "apps.core",
    "apps.accounts",
    "apps.tickets",
    "apps.solutions",
    "apps.reports",
    # Fase berikutnya: apps.zabbix
]

INSTALLED_APPS = DJANGO_APPS + LOCAL_APPS

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.tickets.middleware.AutoEscalateMiddleware",
]

# Aturan waktu tiket
TICKET_AUTO_OUTSTANDING_MINUTES = 60  # Open → Outstanding otomatis setelah 1 jam
TICKET_CLOSED_EDIT_MINUTES = 10       # Agent masih boleh ubah tiket closed 10 menit

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.core.context_processors.app_meta",
                "apps.core.context_processors.ui_state",
            ],
        },
    },
]


# ── Database ──────────────────────────────────────────────────────────────
# Default SQLite supaya bisa langsung jalan tanpa setup.
# Produksi/Docker: set DATABASE_URL=postgres://user:pass@host:5432/dbname

DATABASES = {"default": env.db("DATABASE_URL")}
DATABASES["default"]["ATOMIC_REQUESTS"] = True


# ── Autentikasi ───────────────────────────────────────────────────────────

AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
     "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "core:dashboard"
LOGOUT_REDIRECT_URL = "accounts:login"

SESSION_COOKIE_AGE = 60 * 60 * 8  # 8 jam = satu shift kerja
SESSION_SAVE_EVERY_REQUEST = True


# ── Lokalisasi ────────────────────────────────────────────────────────────

LANGUAGE_CODE = "id"
TIME_ZONE = "Asia/Jakarta"
USE_I18N = True
USE_TZ = True

# Format tanggal/jam yang dipakai konsisten di UI dan Excel
DATETIME_DISPLAY_FORMAT = "%d/%m/%Y %H:%M"
DATE_DISPLAY_FORMAT = "%d/%m/%Y"


# ── File statis & media ───────────────────────────────────────────────────

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Batas upload lampiran tiket (10 MB)
MAX_UPLOAD_SIZE_MB = 10
DATA_UPLOAD_MAX_MEMORY_SIZE = MAX_UPLOAD_SIZE_MB * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = MAX_UPLOAD_SIZE_MB * 1024 * 1024


# ── Identitas aplikasi (dipakai di UI & header Excel) ─────────────────────

APP_NAME = "Ticketing NMS"
COMPANY_NAME = "PT Ideologi Nusa Integrasi"
COMPANY_SHORT = "INITECH"
APP_VERSION = "0.2.0"


# ── Single Sign-On Office 365 ─────────────────────────────────────────────
# Integrasi SAML 2.0 / OIDC sesungguhnya menyusul setelah tenant & app
# registration dari tim IT tersedia. Selama DEMO_MODE aktif, tombol SSO
# memakai jalur bypass lokal supaya alur login tetap bisa diperagakan.

SSO = {
    "ENABLED": True,
    "PROVIDER": "Microsoft 365",
    "PROTOCOL": env("SSO_PROTOCOL", default="OIDC"),
    "TENANT_DOMAIN": env("SSO_TENANT_DOMAIN", default="initech.co.id"),
    "DEMO_MODE": env.bool("SSO_DEMO_MODE", default=True),
    "DEMO_USERNAME": env("SSO_DEMO_USERNAME", default="rizky.pratama"),
}


# ── Integrasi Zabbix (dipakai mulai Fase 2) ───────────────────────────────

ZABBIX = {
    "URL": env("ZABBIX_URL"),
    "API_TOKEN": env("ZABBIX_API_TOKEN"),
    "USERNAME": env("ZABBIX_USERNAME"),
    "PASSWORD": env("ZABBIX_PASSWORD"),
    "VERIFY_SSL": env("ZABBIX_VERIFY_SSL"),
    "TIMEOUT": env("ZABBIX_TIMEOUT"),
}


# ── Logging ───────────────────────────────────────────────────────────────

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{asctime} [{levelname}] {name}: {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "django.db.backends": {"level": "WARNING", "propagate": False,
                               "handlers": ["console"]},
        "apps": {"level": "DEBUG", "propagate": False, "handlers": ["console"]},
    },
}
