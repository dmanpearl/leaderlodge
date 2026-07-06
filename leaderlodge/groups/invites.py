import logging
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AbstractBaseUser
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.template import loader
from django.utils import timezone

from leaderlodge.core.admin_notifications import (
    notify_admin_invite_accepted,
    notify_admin_invite_sent,
)
from leaderlodge.groups.models import Group, GroupInvite, GroupMembership, GroupPlayer
from leaderlodge.groups.names import format_user_display_name
from leaderlodge.groups.services import (
    add_guest_player,
    remove_roster_player,
    user_is_member,
)

User = get_user_model()
logger = logging.getLogger(__name__)

INVITE_EXPIRY_DAYS = 7


def player_name_default_from_email(email: str) -> str:
    local = email.split("@", 1)[0]
    first = local.split(".")[0].split("_")[0].strip()
    return (first.title() or "Guest")[:100]


def default_first_name_for_invite(invite: GroupInvite) -> str:
    if invite.guest_player_id and invite.guest_player is not None:
        return invite.guest_player.display_name
    if invite.email:
        return player_name_default_from_email(invite.email)
    return ""


def _expires_at():
    return timezone.now() + timedelta(days=INVITE_EXPIRY_DAYS)


def _new_token() -> str:
    return secrets.token_urlsafe(32)


def build_invite_url(request, invite: GroupInvite) -> str:
    from django.urls import reverse

    path = reverse("groups:invite_accept", kwargs={"token": invite.token})
    return request.build_absolute_uri(path)


def pending_invites_for_group(group: Group):
    now = timezone.now()
    return group.invites.filter(
        kind=GroupInvite.Kind.EMAIL,
        accepted_at__isnull=True,
        revoked_at__isnull=True,
        expires_at__gt=now,
    ).select_related("guest_player", "invited_by")


def pending_invite_for_email(group: Group, email: str) -> GroupInvite | None:
    now = timezone.now()
    return (
        group.invites.filter(
            kind=GroupInvite.Kind.EMAIL,
            email__iexact=email.strip(),
            accepted_at__isnull=True,
            revoked_at__isnull=True,
            expires_at__gt=now,
        )
        .select_related("guest_player")
        .first()
    )


def _revoke_pending_email_invites(*, group: Group, email: str) -> None:
    for invite in group.invites.filter(
        kind=GroupInvite.Kind.EMAIL,
        email__iexact=email,
        accepted_at__isnull=True,
        revoked_at__isnull=True,
    ):
        revoke_group_invite(invite=invite)


def _unique_guest_name(group: Group, base_name: str) -> str:
    name = base_name.strip()[:100]
    if not name:
        name = "Guest"
    if not group.players.filter(display_name__iexact=name).exists():
        return name
    for index in range(2, 100):
        candidate = f"{name} {index}"[:100]
        if not group.players.filter(display_name__iexact=candidate).exists():
            return candidate
    raise ValueError(f"Could not allocate guest name for {base_name!r}.")


def _pending_invite_for_guest(guest_player: GroupPlayer) -> GroupInvite | None:
    now = timezone.now()
    return GroupInvite.objects.filter(
        guest_player=guest_player,
        accepted_at__isnull=True,
        revoked_at__isnull=True,
        expires_at__gt=now,
    ).first()


@transaction.atomic
def create_email_invite(
    *,
    group: Group,
    email: str,
    invited_by: AbstractBaseUser,
    player_name: str = "",
) -> GroupInvite:
    normalized_email = email.strip().lower()
    if user_is_member_by_email(group, normalized_email):
        raise ValueError("That email already belongs to a group member.")
    if pending_invite_for_email(group, normalized_email) is not None:
        raise ValueError("An invite is already pending for that email.")

    display_name = _unique_guest_name(
        group,
        player_name.strip() or player_name_default_from_email(normalized_email),
    )
    guest = add_guest_player(group=group, display_name=display_name)
    invite = GroupInvite.objects.create(
        group=group,
        kind=GroupInvite.Kind.EMAIL,
        email=normalized_email,
        invited_by=invited_by,
        token=_new_token(),
        guest_player=guest,
        expires_at=_expires_at(),
    )
    return invite


@transaction.atomic
def create_email_invite_for_guest(
    *,
    group: Group,
    guest_player: GroupPlayer,
    email: str,
    invited_by: AbstractBaseUser,
) -> GroupInvite:
    if guest_player.group_id != group.pk:
        raise ValueError("That player is not on this group's roster.")
    if guest_player.linked_user_id:
        raise ValueError("That player is already linked to an account.")
    if _pending_invite_for_guest(guest_player) is not None:
        raise ValueError("An invite is already pending for this player.")

    normalized_email = email.strip().lower()
    if user_is_member_by_email(group, normalized_email):
        raise ValueError("That email already belongs to a group member.")
    pending = pending_invite_for_email(group, normalized_email)
    if pending is not None and pending.guest_player_id != guest_player.pk:
        raise ValueError("An invite is already pending for that email.")

    return GroupInvite.objects.create(
        group=group,
        kind=GroupInvite.Kind.EMAIL,
        email=normalized_email,
        invited_by=invited_by,
        token=_new_token(),
        guest_player=guest_player,
        guest_preexisting=True,
        expires_at=_expires_at(),
    )


def user_is_member_by_email(group: Group, email: str) -> bool:
    return GroupMembership.objects.filter(
        group=group,
        user__email__iexact=email.strip(),
    ).exists()


def invite_for_token(token: str) -> GroupInvite | None:
    return (
        GroupInvite.objects.select_related("group", "guest_player", "invited_by")
        .filter(token=token)
        .first()
    )


def invite_email_matches_user(invite: GroupInvite, user: AbstractBaseUser) -> bool:
    user_email = (user.email or "").strip().lower()
    return user_email == invite.email.strip().lower()


def _manager_emails(group: Group) -> list[str]:
    emails = set(
        User.objects.filter(
            group_memberships__group=group,
            group_memberships__role__in=(
                GroupMembership.Role.OWNER,
                GroupMembership.Role.EDITOR,
            ),
        )
        .exclude(email="")
        .values_list("email", flat=True)
    )
    return sorted(emails)


def notify_managers_invite_accepted(
    *,
    invite: GroupInvite,
    user: AbstractBaseUser,
    roster_name: str,
) -> None:
    chosen_first = (user.first_name or "").strip()
    if not roster_name or chosen_first.lower() == roster_name.strip().lower():
        return

    recipients = _manager_emails(invite.group)
    if invite.invited_by.email:
        recipients = sorted(set(recipients) | {invite.invited_by.email})

    if not recipients:
        return

    context = {
        "group": invite.group,
        "user": user,
        "display_name": format_user_display_name(user),
        "email": user.email,
        "roster_name": roster_name,
        "chosen_first_name": chosen_first,
    }
    subject = loader.render_to_string(
        "groups/invite_accepted_notify_subject.txt", context
    )
    subject = "".join(subject.splitlines())
    body = loader.render_to_string("groups/invite_accepted_notify_email.txt", context)
    email_message = EmailMultiAlternatives(
        subject,
        body,
        settings.DEFAULT_FROM_EMAIL,
        recipients,
    )
    try:
        email_message.send()
        logger.info(
            "Notified group managers about invite acceptance for group pk %s",
            invite.group_id,
        )
    except Exception:
        logger.exception(
            "Failed to notify managers about invite acceptance for group pk %s",
            invite.group_id,
        )


@transaction.atomic
def accept_group_invite(
    *,
    invite: GroupInvite,
    user: AbstractBaseUser,
    first_name: str | None = None,
    last_name: str | None = None,
) -> GroupMembership:
    if not invite.is_pending:
        raise ValueError("This invite is no longer valid.")
    if not invite_email_matches_user(invite, user):
        raise ValueError("This invite was sent to a different email address.")

    roster_name = ""
    if invite.guest_player_id and invite.guest_player is not None:
        roster_name = invite.guest_player.display_name

    update_fields: list[str] = []
    if first_name is not None:
        user.first_name = first_name.strip()
        update_fields.append("first_name")
    elif not (user.first_name or "").strip() and roster_name:
        user.first_name = roster_name
        update_fields.append("first_name")
    if last_name is not None:
        user.last_name = last_name.strip()
        update_fields.append("last_name")
    if update_fields:
        user.save(update_fields=update_fields)

    if user_is_member(user, invite.group):
        invite.accepted_at = timezone.now()
        invite.accepted_by = user
        invite.save(update_fields=["accepted_at", "accepted_by"])
        return GroupMembership.objects.get(group=invite.group, user=user)

    membership = GroupMembership.objects.create(
        group=invite.group,
        user=user,
        role=GroupMembership.Role.MEMBER,
    )
    if invite.guest_player_id:
        player = invite.guest_player
        if player is not None:
            player.linked_user = user
            player.is_active = True
            player.save(update_fields=["linked_user", "is_active"])
    else:
        from leaderlodge.groups.services import _get_or_create_linked_player

        _get_or_create_linked_player(group=invite.group, user=user)

    invite.accepted_at = timezone.now()
    invite.accepted_by = user
    invite.save(update_fields=["accepted_at", "accepted_by"])

    notify_managers_invite_accepted(
        invite=invite,
        user=user,
        roster_name=roster_name,
    )
    notify_admin_invite_accepted(
        invite=invite,
        user=user,
        roster_name=roster_name,
    )
    return membership


@transaction.atomic
def revoke_group_invite(*, invite: GroupInvite) -> None:
    if invite.revoked_at is not None or invite.accepted_at is not None:
        return
    invite.revoked_at = timezone.now()
    invite.save(update_fields=["revoked_at"])
    if invite.guest_player_id:
        player = GroupPlayer.objects.filter(pk=invite.guest_player_id).first()
        if (
            player is not None
            and player.linked_user_id is None
            and not invite.guest_preexisting
        ):
            remove_roster_player(player=player)


def send_invite_email(*, request, invite: GroupInvite) -> None:
    if not invite.email:
        raise ValueError("Invite has no email address.")

    accept_url = build_invite_url(request, invite)
    context = {
        "invite": invite,
        "group": invite.group,
        "invited_by": invite.invited_by,
        "accept_url": accept_url,
        "player_name": invite.guest_player.display_name if invite.guest_player else "",
    }
    subject = loader.render_to_string("groups/invite_subject.txt", context)
    subject = "".join(subject.splitlines())
    body = loader.render_to_string("groups/invite_email.txt", context)
    email_message = EmailMultiAlternatives(
        subject,
        body,
        settings.DEFAULT_FROM_EMAIL,
        [invite.email],
    )
    try:
        email_message.send()
        logger.info(
            "Sent group invite email to %s for group pk %s",
            invite.email,
            invite.group_id,
        )
    except Exception:
        logger.exception(
            "Group invite email delivery failed for group pk %s",
            invite.group_id,
        )
        raise

    player_name = invite.guest_player.display_name if invite.guest_player else ""
    notify_admin_invite_sent(
        invite=invite,
        invited_by_display=format_user_display_name(invite.invited_by),
        player_name=player_name,
        invite_url=accept_url,
    )
