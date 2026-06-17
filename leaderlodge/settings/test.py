"""Test settings — used by pytest only."""

import os

os.environ.setdefault("DJANGO_SECRET_KEY", "test-secret-key-not-for-production")

from .base import *  # noqa: E402, F403

DEBUG = True
