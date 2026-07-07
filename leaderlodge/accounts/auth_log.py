"""Record and query the auth-event-log (signups, invites, password, login)."""

from __future__ import annotations

import logging
from typing import Any

from django.contrib.auth.models import AbstractBaseUser, AnonymousUser
from django.http import HttpRequest
from django.urls import reverse

from leaderlodge.accounts.honeypot import client_ip
from leaderlodge.accounts.models import AuthEvent

logger = logging.getLogger(__name__)

# Hardcoded switch: flip to False if failed-signup validation rows create too
# much log noise. Everything else in the auth-event-log stays on.
LOG_FAILED_SIGNUPS = True

_USER_AGENT_MAX = 400

# Event types that represent a blocked or failed outcome. Anything not listed
# here defaults to a success outcome.
_BLOCKED_EVENTS = {AuthEvent.EventType.SIGNUP_BLOCKED}
_FAILURE_EVENTS = {
    AuthEvent.EventType.SIGNUP_FAILED,
    AuthEvent.EventType.LOGIN_FAILED,
}


def _default_outcome(event_type: str) -> str:
    if event_type in _BLOCKED_EVENTS:
        return AuthEvent.Outcome.BLOCKED
    if event_type in _FAILURE_EVENTS:
        return AuthEvent.Outcome.FAILURE
    return AuthEvent.Outcome.SUCCESS


def _resolve_user(
    user: AbstractBaseUser | AnonymousUser | None,
) -> AbstractBaseUser | None:
    if user is None:
        return None
    if getattr(user, "is_authenticated", False):
        return user  # type: ignore[return-value]
    return None


def _user_agent(request: HttpRequest | None) -> str:
    if request is None:
        return ""
    agent = (request.META.get("HTTP_USER_AGENT") or "").strip()
    if len(agent) > _USER_AGENT_MAX:
        return f"{agent[: _USER_AGENT_MAX - 3]}..."
    return agent


def record_auth_event(
    *,
    event_type: str,
    request: HttpRequest | None = None,
    user: AbstractBaseUser | AnonymousUser | None = None,
    email: str = "",
    source: str = "",
    reason: str = "",
    outcome: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> AuthEvent | None:
    """Persist one auth-event-log row. Never raises; logging must not break auth."""
    try:
        return AuthEvent.objects.create(
            event_type=event_type,
            outcome=outcome or _default_outcome(event_type),
            user=_resolve_user(user),
            email=(email or "").strip().lower(),
            ip_address=client_ip(request) if request is not None else "",
            user_agent=_user_agent(request),
            source=source,
            reason=reason,
            metadata=metadata or {},
        )
    except Exception:
        logger.exception("Failed to record auth event %s", event_type)
        return None


def log_failed_signup(request: HttpRequest, form, *, source: str) -> AuthEvent | None:
    """Record a failed signup validation attempt when the switch is on."""
    if not LOG_FAILED_SIGNUPS:
        return None
    email = str((form.data or {}).get("email", "")).strip().lower()
    field_errors = sorted(key for key in form.errors if key != "__all__")
    return record_auth_event(
        event_type=AuthEvent.EventType.SIGNUP_FAILED,
        request=request,
        email=email,
        source=source,
        reason="validation_error",
        metadata={"fields": field_errors} if field_errors else {},
    )


def admin_event_url(request: HttpRequest | None, event: AuthEvent | None) -> str:
    """Absolute admin change URL for an AuthEvent, or empty string."""
    if event is None:
        return ""
    try:
        path = reverse("admin:accounts_authevent_change", args=[event.pk])
    except Exception:
        return ""
    if request is not None:
        return request.build_absolute_uri(path)
    return path
