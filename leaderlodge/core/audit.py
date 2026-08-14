"""Registry of known audit event types and the shared logging helper."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django.contrib.contenttypes.models import ContentType
from django.db.models import Model

from leaderlodge.core.models import AuditLog

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractBaseUser
    from django.http import HttpRequest

# Maintained for readability and to catch typos at call sites. event_type is
# a plain string at the model/DB level, so new entries here never require a
# migration.
EVENT_SPECTATOR_MODE_ENTERED = "spectator_mode.entered"
EVENT_SPECTATOR_MODE_EXITED = "spectator_mode.exited"

KNOWN_EVENT_TYPES = {
    EVENT_SPECTATOR_MODE_ENTERED: "Spectator Mode entered",
    EVENT_SPECTATOR_MODE_EXITED: "Spectator Mode exited",
}


def log_event(
    *,
    event_type: str,
    actor: "AbstractBaseUser | None" = None,
    target: Model | None = None,
    payload: dict[str, Any] | None = None,
    request: "HttpRequest | None" = None,
) -> AuditLog:
    content_type = None
    object_id = None
    if target is not None:
        content_type = ContentType.objects.get_for_model(target)
        object_id = target.pk

    ip_address = None
    session_key = ""
    if request is not None:
        ip_address = request.META.get("REMOTE_ADDR")
        session_key = request.session.session_key or ""
        if actor is None and request.user.is_authenticated:
            actor = request.user

    return AuditLog.objects.create(
        actor=actor,
        event_type=event_type,
        content_type=content_type,
        object_id=object_id,
        payload=payload or {},
        ip_address=ip_address,
        session_key=session_key,
    )
