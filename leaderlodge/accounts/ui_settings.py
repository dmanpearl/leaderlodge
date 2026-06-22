"""
Central helpers for per-user UI preference persistence.

Storage: UserProfile.ui_settings (JSONField, dict keyed by namespace slug)
"""

from __future__ import annotations

from typing import Any


def _profile(user):
    from leaderlodge.accounts.models import UserProfile

    profile, _ = UserProfile.objects.get_or_create(user=user)
    return profile


def get_ui_settings(user, namespace: str) -> dict:
    profile = _profile(user)
    blob = profile.ui_settings or {}
    return dict(blob.get(namespace, {}))


def set_ui_settings(user, namespace: str, data: dict[str, Any]) -> None:
    profile = _profile(user)
    blob = dict(profile.ui_settings or {})
    existing = dict(blob.get(namespace, {}))
    existing.update(data)
    blob[namespace] = existing
    profile.ui_settings = blob
    profile.save(update_fields=["ui_settings"])


def reset_ui_settings(user, namespace: str | None = None) -> None:
    profile = _profile(user)
    if namespace is None:
        profile.ui_settings = {}
    else:
        blob = dict(profile.ui_settings or {})
        blob.pop(namespace, None)
        profile.ui_settings = blob
    profile.save(update_fields=["ui_settings"])
