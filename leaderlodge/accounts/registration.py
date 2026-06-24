"""Helpers for creating accounts from signup."""

from __future__ import annotations

import re

from django.contrib.auth.models import User

USERNAME_MAX_LENGTH = 150


def username_base_from_email(email: str) -> str:
    local = email.split("@", 1)[0].lower()
    base = re.sub(r"[^\w.+@-]", "", local).strip(".@+-_")
    return (base or "user")[:USERNAME_MAX_LENGTH]


def unique_username_for_email(email: str) -> str:
    base = username_base_from_email(email)
    if not User.objects.filter(username=base).exists():
        return base

    for suffix in range(2, 1000):
        candidate = f"{base}{suffix}"[:USERNAME_MAX_LENGTH]
        if not User.objects.filter(username=candidate).exists():
            return candidate

    raise RuntimeError("Could not allocate a unique username.")
