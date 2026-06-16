from django.contrib.auth.models import AbstractBaseUser

from leaderlodge.groups.locations import create_location_library
from leaderlodge.groups.models import Group, GroupMembership, GroupPlayer
from leaderlodge.groups.names import format_user_display_name


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
    players = group.players.filter(is_active=True).select_related("linked_user")
    for player in players:
        if player.display_name.lower() == seed_lower:
            return player
        linked_user = player.linked_user
        if linked_user is None:
            continue
        if linked_user.get_username().lower() == seed_lower:
            return player
        first_name = (linked_user.first_name or "").strip().lower()
        if first_name and first_name == seed_lower:
            return player

    return add_guest_player(group=group, display_name=cleaned)


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


def add_guest_player(*, group: Group, display_name: str) -> GroupPlayer:
    return GroupPlayer.objects.create(
        group=group,
        display_name=display_name.strip(),
    )
