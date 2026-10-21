"""
Rate limiting and lockout protection against brute-force attacks on authentication endpoints.
"""

from django.core.cache import cache

LOGIN_ATTEMPT_LIMIT = 5       # Maximum failed login attempts allowed
LOGIN_LOCKOUT_SECONDS = 900   # 15 minutes lockout duration (900 seconds)


def get_client_ip(request):
    """Retrieve real client IP even when behind reverse proxies."""
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "unknown")


def is_locked_out(request, username=None):
    """
    Check if the client IP or target username is currently locked out.
    Returns (is_locked: bool, error_message: str).
    """
    ip = get_client_ip(request)
    if cache.get(f"login_lockout_ip:{ip}"):
        return True, "Too many failed login attempts from this IP address. Please wait 15 minutes before trying again."

    if username and cache.get(f"login_lockout_user:{username.lower()}"):
        return True, "Too many failed login attempts for this account. Please wait 15 minutes before trying again."

    return False, ""


def record_failed_login(request, username=None):
    """Record a failed login attempt for the client IP and username."""
    ip = get_client_ip(request)

    # Track attempts per IP
    ip_key = f"login_attempts_ip:{ip}"
    ip_attempts = (cache.get(ip_key) or 0) + 1
    cache.set(ip_key, ip_attempts, LOGIN_LOCKOUT_SECONDS)
    if ip_attempts >= LOGIN_ATTEMPT_LIMIT:
        cache.set(f"login_lockout_ip:{ip}", True, LOGIN_LOCKOUT_SECONDS)

    # Track attempts per Username
    if username:
        user_key = f"login_attempts_user:{username.lower()}"
        user_attempts = (cache.get(user_key) or 0) + 1
        cache.set(user_key, user_attempts, LOGIN_LOCKOUT_SECONDS)
        if user_attempts >= LOGIN_ATTEMPT_LIMIT:
            cache.set(f"login_lockout_user:{username.lower()}", True, LOGIN_LOCKOUT_SECONDS)


def clear_failed_logins(request, username=None):
    """Clear failed attempts and lockout upon successful authentication."""
    ip = get_client_ip(request)
    cache.delete(f"login_attempts_ip:{ip}")
    cache.delete(f"login_lockout_ip:{ip}")

    if username:
        cache.delete(f"login_attempts_user:{username.lower()}")
        cache.delete(f"login_lockout_user:{username.lower()}")
