from django.contrib.auth.models import AbstractBaseUser

from leaderlodge.groups.locations import create_location_library
from leaderlodge.groups.models import Group, GroupMembership, GroupPlayer


def player_display_name(user: AbstractBaseUser) -> str:
    full_name = user.get_full_name().strip()
    return full_name or user.get_username()


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
