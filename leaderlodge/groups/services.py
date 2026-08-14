from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser
from django.db import IntegrityError, transaction
from django.db.models import Q

from leaderlodge.groups.locations import create_location_library
from leaderlodge.groups.models import Group, GroupMembership, GroupPlayer
from leaderlodge.groups.names import format_user_display_name
from leaderlodge.groups.permissions import can_manage_members, get_membership


def player_display_name(user: AbstractBaseUser) -> str:
    return format_user_display_name(user)


def resolve_group(identifier: str) -> Group:
    if identifier.isdigit():
        group = Group.objects.filter(pk=int(identifier)).first()
        if group is None:
            raise Group.DoesNotExist(f"No group with id {identifier}.")
        return group

    group = Group.objects.filter(name=identifier).first()
    if group is None:
        raise Group.DoesNotExist(f"No group named {identifier!r}.")
    return group


def resolve_seed_player(*, group: Group, seed_name: str) -> GroupPlayer:
    cleaned = seed_name.strip()
    if not cleaned:
        raise ValueError("Seed player name cannot be empty.")

    seed_lower = cleaned.lower()
    players = list(group.players.select_related("linked_user"))

    for player in players:
        linked_user = player.linked_user
        if linked_user is None:
            continue
        if linked_user.get_username().lower() == seed_lower:
            return player

    for player in players:
        linked_user = player.linked_user
        if linked_user is None:
            continue
        first_name = (linked_user.first_name or "").strip().lower()
        if first_name and first_name == seed_lower:
            return player

    for player in players:
        if player.display_name.lower() == seed_lower:
            return player

    for membership in group.memberships.select_related("user"):
        user = membership.user
        if user.get_username().lower() == seed_lower:
            return _get_or_create_linked_player(group=group, user=user)
        first_name = (user.first_name or "").strip().lower()
        if first_name and first_name == seed_lower:
            return _get_or_create_linked_player(group=group, user=user)

    try:
        return add_guest_player(group=group, display_name=cleaned)
    except IntegrityError:
        return _resolve_seed_player_after_conflict(group=group, cleaned=cleaned)


def _link_guest_player(
    *, group: Group, user: AbstractBaseUser, display_name: str
) -> GroupPlayer | None:
    player = group.players.filter(
        display_name__iexact=display_name,
        linked_user__isnull=True,
    ).first()
    if player is None:
        first_name = (user.first_name or "").strip()
        if first_name:
            player = group.players.filter(
                display_name__iexact=first_name,
                linked_user__isnull=True,
            ).first()
    if player is None:
        return None
    player.linked_user = user
    player.save(update_fields=["linked_user"])
    return player


def _get_or_create_linked_player(
    *, group: Group, user: AbstractBaseUser
) -> GroupPlayer:
    player = group.players.filter(linked_user=user).first()
    if player is not None:
        return player

    display_name = player_display_name(user)
    linked = _link_guest_player(group=group, user=user, display_name=display_name)
    if linked is not None:
        return linked

    try:
        return GroupPlayer.objects.create(
            group=group,
            display_name=display_name,
            linked_user=user,
        )
    except IntegrityError:
        player = group.players.filter(linked_user=user).first()
        if player is not None:
            return player
        linked = _link_guest_player(group=group, user=user, display_name=display_name)
        if linked is not None:
            return linked
        raise


def _resolve_seed_player_after_conflict(*, group: Group, cleaned: str) -> GroupPlayer:
    seed_lower = cleaned.lower()

    player = group.players.filter(display_name__iexact=cleaned).first()
    if player is not None:
        return player

    for player in group.players.select_related("linked_user"):
        linked_user = player.linked_user
        if linked_user is None:
            continue
        if linked_user.get_username().lower() == seed_lower:
            return player
        first_name = (linked_user.first_name or "").strip().lower()
        if first_name and first_name == seed_lower:
            return player

    raise IntegrityError(
        f"Could not resolve seed player {cleaned!r} for group {group.name!r}."
    )


def create_group_with_owner(
    *, user: AbstractBaseUser, name: str, description: str = ""
) -> Group:
    location_library = create_location_library(
        user=user,
        name=f"{name} places",
    )
    group = Group.objects.create(
        name=name,
        description=description,
        created_by=user,
        location_library=location_library,
    )
    GroupMembership.objects.create(
        group=group,
        user=user,
        role=GroupMembership.Role.OWNER,
    )
    GroupPlayer.objects.create(
        group=group,
        display_name=player_display_name(user),
        linked_user=user,
    )
    return group


def user_groups(user: AbstractBaseUser):
    return Group.objects.filter(memberships__user=user).distinct()


def get_demo_group() -> Group | None:
    if not settings.DEMO_MODE_ENABLED:
        return None
    return Group.objects.filter(is_demo=True).order_by("pk").first()


def demo_group_exists() -> bool:
    return get_demo_group() is not None


def can_view_group(user: AbstractBaseUser | None, group: Group) -> bool:
    if group.is_demo and settings.DEMO_MODE_ENABLED:
        return True
    if user is None or not user.is_authenticated:
        return False
    if user.is_staff:
        return True
    return user_is_member(user, group)


def can_edit_group(user: AbstractBaseUser | None, group: Group) -> bool:
    if user is None or not user.is_authenticated:
        return False
    if group.is_demo:
        return user.is_staff or group.created_by_id == user.pk
    return user_is_member(user, group)


def can_manage_group_members(user: AbstractBaseUser | None, group: Group) -> bool:
    if group.is_demo:
        return False
    return can_manage_members(get_membership(user, group))


def visible_groups(user: AbstractBaseUser | None):
    group_ids: set[int] = set()
    if user and user.is_authenticated:
        group_ids.update(user_groups(user).values_list("pk", flat=True))
    demo = get_demo_group()
    if demo is not None:
        group_ids.add(demo.pk)
    return Group.objects.filter(pk__in=group_ids).order_by("name")


def editable_groups(user: AbstractBaseUser | None):
    """Membership groups plus demo groups the user may edit (staff or creator)."""
    if user is None or not user.is_authenticated:
        return Group.objects.none()

    member_non_demo = Q(memberships__user=user, is_demo=False)
    if user.is_staff:
        demo_editable = Q(is_demo=True)
    else:
        demo_editable = Q(is_demo=True, created_by=user)
    return (
        Group.objects.filter(member_non_demo | demo_editable)
        .distinct()
        .order_by("name")
    )


def user_is_member(user: AbstractBaseUser, group: Group) -> bool:
    return GroupMembership.objects.filter(group=group, user=user).exists()


def single_user_group(user: AbstractBaseUser) -> Group | None:
    groups = list(user_groups(user).order_by("name"))
    if len(groups) == 1:
        return groups[0]
    return None


def resolve_user_group(user: AbstractBaseUser, group_id: str | None) -> Group | None:
    if group_id:
        group = Group.objects.filter(pk=group_id).first()
        if group and user_is_member(user, group):
            return group
        return None
    return single_user_group(user)


def resolve_view_group(
    user: AbstractBaseUser | None, group_id: str | None
) -> Group | None:
    if group_id:
        group = Group.objects.filter(pk=group_id).first()
        if group and can_view_group(user, group):
            return group
        return None
    if user and user.is_authenticated:
        return single_user_group(user)
    return get_demo_group()


def add_guest_player(*, group: Group, display_name: str) -> GroupPlayer:
    return GroupPlayer.objects.create(
        group=group,
        display_name=display_name.strip(),
    )


def add_group_member(
    *,
    group: Group,
    user: AbstractBaseUser,
    role: str = GroupMembership.Role.MEMBER,
) -> GroupMembership:
    with transaction.atomic():
        membership = GroupMembership.objects.create(
            group=group,
            user=user,
            role=role,
        )
        _get_or_create_linked_player(group=group, user=user)
    return membership


def _unlink_member_from_roster(*, group: Group, user: AbstractBaseUser) -> None:
    player = group.players.filter(linked_user=user).first()
    if player is None:
        return
    player.linked_user = None
    player.save(update_fields=["linked_user"])


def player_has_games(player: GroupPlayer) -> bool:
    return player.game_results.exists()


def remove_group_member(*, membership: GroupMembership) -> str:
    """Remove membership. Returns ``converted`` or ``removed``."""
    with transaction.atomic():
        player = membership.group.players.filter(linked_user=membership.user).first()
        if player is not None and player_has_games(player):
            _unlink_member_from_roster(group=membership.group, user=membership.user)
            membership.delete()
            return "converted"
        membership.delete()
        if player is not None:
            player.delete()
        return "removed"


def remove_roster_player(*, player: GroupPlayer) -> None:
    if player_has_games(player):
        raise ValueError("Cannot remove a player with recorded games.")
    if (
        player.linked_user_id
        and GroupMembership.objects.filter(
            group_id=player.group_id,
            user_id=player.linked_user_id,
        ).exists()
    ):
        raise ValueError("Remove the member from the group instead.")
    player.delete()
