"""Auth signal receivers that feed the auth-event-log."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.contrib.auth.signals import user_login_failed
from django.dispatch import receiver

User = get_user_model()


@receiver(user_login_failed)
def _record_login_failure(sender, credentials, request=None, **kwargs) -> None:
    from leaderlodge.accounts.auth_log import record_auth_event
    from leaderlodge.accounts.models import AuthEvent

    attempted = (credentials or {}).get("username", "")
    matched = None
    if attempted:
        matched = (
            User.objects.filter(username__iexact=attempted).first()
            or User.objects.filter(email__iexact=attempted).first()
        )
    record_auth_event(
        event_type=AuthEvent.EventType.LOGIN_FAILED,
        request=request,
        user=matched,
        email=attempted if "@" in str(attempted) else "",
        source="login",
        reason="bad_credentials",
        metadata={"attempted": str(attempted)[:150]},
    )
