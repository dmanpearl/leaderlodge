"""Signup honeypot: hidden decoy field and minimum submit timing."""

from __future__ import annotations

import time
from typing import Any

from django import forms
from django.conf import settings
from django.http import HttpRequest

HONEYPOT_FIELD = "company_website"
TIMING_FIELD = "form_rendered_at"
MIN_SUBMIT_SECONDS = 3
GENERIC_SIGNUP_ERROR = "Unable to create your account. Please try again."


def honeypot_enabled() -> bool:
    return getattr(settings, "HONEYPOT_ENABLED", True)


def add_honeypot_fields(form: forms.Form) -> None:
    if not honeypot_enabled():
        return
    form.fields[HONEYPOT_FIELD] = forms.CharField(
        required=False,
        label="Company website",
        widget=forms.TextInput(
            attrs={
                "class": "honeypot-field",
                "tabindex": "-1",
                "autocomplete": "off",
            }
        ),
    )
    form.fields[TIMING_FIELD] = forms.CharField(
        required=False,
        widget=forms.HiddenInput(),
        initial="" if form.is_bound else str(int(time.time())),
    )


def honeypot_post_data(data: dict[str, Any]) -> dict[str, Any]:
    """Merge honeypot fields into test or client POST payloads."""
    if not honeypot_enabled():
        return dict(data)
    merged = dict(data)
    merged.setdefault(HONEYPOT_FIELD, "")
    merged.setdefault(TIMING_FIELD, str(int(time.time()) - MIN_SUBMIT_SECONDS - 1))
    return merged


def honeypot_triggered(data: Any) -> tuple[bool, str]:
    """Return (triggered, reason_code) for raw POST data or a form."""
    if not honeypot_enabled():
        return False, ""
    if hasattr(data, "get"):
        payload = data
    else:
        return False, ""

    if payload.get(HONEYPOT_FIELD, "").strip():
        return True, "honeypot_filled"

    raw_ts = str(payload.get(TIMING_FIELD, "")).strip()
    if not raw_ts.isdigit():
        return True, "missing_timestamp"

    elapsed = time.time() - int(raw_ts)
    if elapsed < MIN_SUBMIT_SECONDS:
        return True, "submitted_too_fast"

    return False, ""


def client_ip(request: HttpRequest) -> str:
    forwarded = (request.META.get("HTTP_X_FORWARDED_FOR") or "").split(",")[0].strip()
    if forwarded:
        return forwarded
    return (request.META.get("REMOTE_ADDR") or "").strip()


def signup_email_from_post(data: Any) -> str:
    if not hasattr(data, "get"):
        return ""
    return str(data.get("email", "")).strip().lower()


def handle_signup_honeypot(
    request: HttpRequest,
    *,
    source: str,
    post_data: Any,
    form: forms.Form,
) -> bool:
    """Notify admins and attach a generic error when the honeypot trips."""
    triggered, reason = honeypot_triggered(post_data)
    if not triggered:
        return False

    from leaderlodge.accounts.auth_log import record_auth_event
    from leaderlodge.accounts.models import AuthEvent
    from leaderlodge.core.admin_notifications import notify_admin_signup_bot_blocked

    email = signup_email_from_post(post_data)
    event = record_auth_event(
        event_type=AuthEvent.EventType.SIGNUP_BLOCKED,
        request=request,
        email=email,
        source=source,
        reason=reason,
    )
    notify_admin_signup_bot_blocked(
        request=request,
        source=source,
        reason=reason,
        email=email,
        event=event,
    )
    form.add_error(None, GENERIC_SIGNUP_ERROR)
    return True
