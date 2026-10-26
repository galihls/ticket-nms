#!/usr/bin/env python
"""Entry point administratif Django untuk Ticketing NMS."""
import os
import sys


def main():
    from pathlib import Path
    try:
        import environ
        env_file = Path(__file__).resolve().parent / ".env"
        if env_file.exists():
            environ.Env.read_env(env_file)
    except Exception:
        pass

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Django tidak ditemukan. Aktifkan virtualenv dulu: source .venv/bin/activate"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
