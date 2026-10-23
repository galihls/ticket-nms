"""Setelan lingkungan pengembangan."""

from .base import *  # noqa: F403

DEBUG = True
ALLOWED_HOSTS = ["*"]

# Mengizinkan tunneling lokal (VS Code Port Forwarding, ngrok, pinggy, cloudflare) untuk testing
CSRF_TRUSTED_ORIGINS = [
    "http://127.0.0.1:8000",
    "http://localhost:8000",
    "https://*.devtunnels.ms",
    "https://*.ngrok-free.app",
    "https://*.trycloudflare.com",
    "https://*.pinggy.link",
    "https://*.a.pinggy.link",
    "https://*.free.pinggy.link",
    "https://*.pinggy-free.link",
    "https://*.run.pinggy-free.link",
    "http://*.pinggy-free.link",
    "http://*.run.pinggy-free.link",
] + env.list("DJANGO_CSRF_TRUSTED_ORIGINS", default=[])

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Manifest storage butuh collectstatic; di dev pakai yang sederhana.
STORAGES["staticfiles"] = {  # noqa: F405
    "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
}

EMAIL_BACKEND = env("EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend")

INTERNAL_IPS = ["127.0.0.1"]
