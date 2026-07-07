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


def notify_admin_signup(*, user: AbstractBaseUser) -> bool:
    from leaderlodge.groups.names import format_user_display_name

    return notify_admin(
        kind="signup",
        context={
            "user": user,
            "display_name": format_user_display_name(user),
            "username": user.username,
            "email": user.email or "",
        },
    )


def notify_admin_invite_sent(
    *,
    invite,
    invited_by_display: str,
    player_name: str = "",
    invite_url: str = "",
) -> bool:
    return notify_admin(
        kind="invite_sent",
        context={
            "invite": invite,
            "group": invite.group,
            "invited_by_display": invited_by_display,
            "player_name": player_name,
            "invite_url": invite_url,
        },
    )


def notify_admin_invite_accepted(
    *,
    invite,
    user: AbstractBaseUser,
    roster_name: str = "",
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
        },
    )


def notify_admin_game_change(*, log) -> bool:
    from django.urls import reverse

    from leaderlodge.games.registry import get_game_type
    from leaderlodge.groups.names import format_user_display_name

    game = log.game
    group = game.group
    changed_by = log.changed_by
    try:
        game_type_label = get_game_type(game.game_type_code).name
    except Exception:
        game_type_label = game.game_type_code

    return notify_admin(
        kind="game_change",
        context={
            "log": log,
            "game": game,
            "group": group,
            "game_type_label": game_type_label,
            "played_on": game.played_on,
            "changed_by_display": format_user_display_name(changed_by),
            "notes": log.notes,
            "game_url": reverse("games:detail", kwargs={"pk": game.pk}),
            "admin_url": reverse(
                "admin:games_gamescorechangelog_change", args=[log.pk]
            ),
        },
    )


def notify_admin_feedback(*, feedback) -> bool:
    from django.urls import reverse

    from leaderlodge.groups.names import format_user_display_name

    user = feedback.user
    return notify_admin(
        kind="feedback",
        context={
            "feedback": feedback,
            "user_display": format_user_display_name(user),
            "admin_url": reverse("admin:feedback_feedback_change", args=[feedback.pk]),
        },
    )


_SIGNUP_BOT_SOURCE_LABELS = {
    "signup": "Open signup",
    "invite_join": "Invite join signup",
}

_SIGNUP_BOT_REASON_LABELS = {
    "honeypot_filled": "Honeypot field trap",
    "submitted_too_fast": "Form submitted too quickly",
    "missing_timestamp": "Missing form timestamp",
}


def notify_admin_signup_bot_blocked(
    *,
    request,
    source: str,
    reason: str,
    email: str = "",
) -> bool:
    from leaderlodge.accounts.honeypot import client_ip

    user_agent = (request.META.get("HTTP_USER_AGENT") or "").strip()
    if len(user_agent) > 300:
        user_agent = f"{user_agent[:297]}..."
    return notify_admin(
        kind="signup_bot_blocked",
        context={
            "source_label": _SIGNUP_BOT_SOURCE_LABELS.get(source, source),
            "reason_label": _SIGNUP_BOT_REASON_LABELS.get(reason, reason),
            "email": email,
            "ip_address": client_ip(request),
            "user_agent": user_agent,
        },
    )
