#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""

import os
import sys


def main():
    """Run administrative tasks."""
    # Default to local settings for development. setdefault() preserves an
    # explicitly set DJANGO_SETTINGS_MODULE, so Railway's production setting
    # still works. If you see production settings locally, check your shell:
    #   grep -r DJANGO_SETTINGS_MODULE ~/.zshrc ~/.bash_profile ~/.bashrc
    #
    # `railway run` from a laptop injects RAILWAY_ENVIRONMENT but not PORT.
    # Use production settings so management commands hit the deployed config.
    if os.environ.get("RAILWAY_ENVIRONMENT") and not os.environ.get("PORT"):
        os.environ.setdefault(
            "DJANGO_SETTINGS_MODULE",
            "leaderlodge.settings.production",
        )
    else:
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "leaderlodge.settings.local")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
