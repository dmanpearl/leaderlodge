from __future__ import annotations

import logging
from typing import Any

from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser
from django.core.mail import EmailMultiAlternatives
from django.template import loader

from leaderlodge.core.admin_notification_registry import (
    DEFAULT_NOTIFICATIONS,
    NOTIFICATION_LABELS,
)
from leaderlodge.core.models import SiteSettings

logger = logging.getLogger(__name__)


def resolved_notifications(stored: dict | None) -> dict[str, bool]:
    stored = stored or {}
    return {key: bool(stored.get(key, False)) for key in NOTIFICATION_LABELS}


def get_site_settings() -> SiteSettings:
    return SiteSettings.load()


def notification_enabled(kind: str) -> bool:
    if kind not in NOTIFICATION_LABELS:
        return False
    config = get_site_settings()
    flags = resolved_notifications(config.notifications)
    return flags.get(kind, False)


def get_notify_email() -> str:
    return (get_site_settings().notify_email or "").strip()


def absolute_site_url() -> str:
    """Public site origin for email links (no trailing slash)."""
    trusted_origins = getattr(settings, "CSRF_TRUSTED_ORIGINS", []) or []
    if not trusted_origins:
        return ""
    return str(trusted_origins[0]).rstrip("/")


def absolute_url(path: str) -> str:
    """Join site origin with a path for clickable notification links."""
    if not path:
        return ""
    if path.startswith(("http://", "https://")):
        return path
    site_url = absolute_site_url()
    if not site_url:
        return path
    if not path.startswith("/"):
        path = f"/{path}"
    return f"{site_url}{path}"


def notify_admin(*, kind: str, context: dict[str, Any]) -> bool:
    """Send an admin notification email when enabled. Never raises."""
    if kind not in NOTIFICATION_LABELS:
        logger.warning("Unknown admin notification kind: %s", kind)
        return False
    if not notification_enabled(kind):
        return False

    recipient = get_notify_email()
    if not recipient:
        logger.warning(
            "Admin notification %s skipped: notify_email is not configured",
            kind,
        )
        return False

    render_context = {
        **context,
        "notification_kind": kind,
        "notification_label": NOTIFICATION_LABELS[kind],
    }
    subject = loader.render_to_string(
        f"core/admin_notifications/{kind}_subject.txt",
        render_context,
    )
    subject = "".join(subject.splitlines())
    body = loader.render_to_string(
        f"core/admin_notifications/{kind}_email.txt",
        render_context,
    )
    email_message = EmailMultiAlternatives(
        subject,
        body,
        settings.DEFAULT_FROM_EMAIL,
        [recipient],
    )
    try:
        email_message.send()
        logger.info("Sent admin notification %s to %s", kind, recipient)
        return True
    except Exception as exc:
        logger.warning(
            "Admin notification %s failed for %s: %s",
            kind,
            recipient,
            exc,
        )
        return False


def geo_context_from_event(event) -> dict[str, str]:
    """Location fields for notification templates, sourced from an AuthEvent."""
    if event is None:
        return {"geo_location": "", "geo_timezone": "", "geo_isp": ""}
    geo_extra = (event.metadata or {}).get("geo") or {}
    return {
        "geo_location": event.geo_label,
        "geo_timezone": str(geo_extra.get("timezone", "")).strip(),
        "geo_isp": str(geo_extra.get("isp", "")).strip(),
    }


def notify_admin_signup(*, user: AbstractBaseUser, event=None) -> bool:
    from leaderlodge.groups.names import format_user_display_name

    return notify_admin(
        kind="signup",
        context={
            "user": user,
            "display_name": format_user_display_name(user),
            "username": user.username,
            "email": user.email or "",
            **geo_context_from_event(event),
        },
    )


def notify_admin_invite_sent(
    *,
    invite,
    invited_by_display: str,
    player_name: str = "",
    invite_url: str = "",
    event=None,
) -> bool:
    return notify_admin(
        kind="invite_sent",
        context={
            "invite": invite,
            "group": invite.group,
            "invited_by_display": invited_by_display,
            "player_name": player_name,
            "invite_url": invite_url,
            **geo_context_from_event(event),
        },
    )


def notify_admin_invite_accepted(
    *,
    invite,
    user: AbstractBaseUser,
    roster_name: str = "",
    event=None,
) -> bool:
    from leaderlodge.groups.names import format_user_display_name

    return notify_admin(
        kind="invite_accepted",
        context={
            "invite": invite,
            "group": invite.group,
            "user": user,
            "display_name": format_user_display_name(user),
            "email": user.email or "",
            "roster_name": roster_name,
            **geo_context_from_event(event),
        },
    )


def _game_log_notification_context(*, log) -> dict[str, Any]:
    from django.urls import reverse

    from leaderlodge.games.registry import get_game_type
    from leaderlodge.groups.names import format_user_display_name

    game = log.game
    snapshot = log.old_snapshot or {}
    if game is not None:
        group = game.group
        group_name = group.name
        game_type_code = game.game_type_code
        played_on = game.played_on
        game_path = reverse("games:detail", kwargs={"pk": game.pk})
        game_url = absolute_url(game_path)
    else:
        group = None
        group_name = (snapshot.get("group") or {}).get("name") or "(unknown group)"
        game_type_code = snapshot.get("game_type_code") or ""
        played_on = snapshot.get("played_on") or ""
        game_url = ""

    try:
        game_type_label = get_game_type(game_type_code).name if game_type_code else ""
    except Exception:
        game_type_label = game_type_code

    # Django admin change URLs include /change/; that is the canonical edit view.
    admin_path = reverse("admin:games_gamescorechangelog_change", args=[log.pk])
    return {
        "log": log,
        "game": game,
        "group": group,
        "group_name": group_name,
        "game_type_label": game_type_label,
        "played_on": played_on,
        "changed_by_display": format_user_display_name(log.changed_by),
        "notes": log.notes,
        "game_url": game_url,
        "admin_url": absolute_url(admin_path),
        "old_snapshot": log.old_snapshot,
        "new_snapshot": log.new_snapshot,
    }


def notify_admin_game_change(*, log) -> bool:
    return notify_admin(
        kind="game_change",
        context=_game_log_notification_context(log=log),
    )


def notify_admin_game_delete(*, log) -> bool:
    return notify_admin(
        kind="game_delete",
        context=_game_log_notification_context(log=log),
    )


def notify_admin_feedback(*, feedback) -> bool:
    from django.urls import reverse

    from leaderlodge.groups.names import format_user_display_name

    user = feedback.user
    # Keep /change/: admin:<app>_<model>_change is the edit page; bare
    # /admin/.../<id>/ is not the reverse target and is unreliable in mail clients.
    admin_path = reverse("admin:feedback_feedback_change", args=[feedback.pk])
    return notify_admin(
        kind="feedback",
        context={
            "feedback": feedback,
            "user_display": format_user_display_name(user),
            "admin_url": absolute_url(admin_path),
        },
    )


_SIGNUP_BOT_SOURCE_LABELS = {
    "signup": "Open signup",
    "invite_join": "Invite join signup",
}

_SIGNUP_BOT_REASON_LABELS = {
    "honeypot_filled": "Honeypot triggered",
    "submitted_too_fast": "Form submitted too quickly",
    "missing_timestamp": "Missing form timestamp",
}


def notify_admin_signup_bot_blocked(
    *,
    request,
    source: str,
    reason: str,
    email: str = "",
    event=None,
    first_name: str = "",
    last_name: str = "",
    trap_value: str = "",
) -> bool:
    from leaderlodge.accounts.auth_log import admin_event_url
    from leaderlodge.accounts.honeypot import client_ip
    from leaderlodge.core.geoip import lookup_ip

    user_agent = (request.META.get("HTTP_USER_AGENT") or "").strip()
    if len(user_agent) > 300:
        user_agent = f"{user_agent[:297]}..."
    geo_context = geo_context_from_event(event)
    if not geo_context["geo_location"]:
        geo_context["geo_location"] = lookup_ip(client_ip(request)).label
    return notify_admin(
        kind="signup_bot_blocked",
        context={
            "source_label": _SIGNUP_BOT_SOURCE_LABELS.get(source, source),
            "reason_label": _SIGNUP_BOT_REASON_LABELS.get(reason, reason),
            "email": email,
            "first_name": first_name,
            "last_name": last_name,
            "trap_value": trap_value,
            "ip_address": client_ip(request),
            "user_agent": user_agent,
            "admin_url": admin_event_url(request, event),
            **geo_context,
        },
    )
