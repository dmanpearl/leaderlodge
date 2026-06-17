"""
Local development settings. Selected by manage.py when DJANGO_SETTINGS_MODULE is unset.
"""

import os

from .base import *  # noqa: F403

DEBUG = True

# Hide runserver production warning in local dev only.
os.environ.setdefault("DJANGO_RUNSERVER_HIDE_WARNING", "true")
