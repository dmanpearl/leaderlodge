from django.contrib.auth.models import AbstractBaseUser

from leaderlodge.groups.models import Group, GroupMembership, GroupPlayer


def player_display_name(user: AbstractBaseUser) -> str:
    full_name = user.get_full_name().strip()
    return full_name or user.get_username()


def create_group_with_owner(
    *, user: AbstractBaseUser, name: str, description: str = ""
) -> Group:
    group = Group.objects.create(
        name=name,
        description=description,
        created_by=user,
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


def add_guest_player(*, group: Group, display_name: str) -> GroupPlayer:
    return GroupPlayer.objects.create(
        group=group,
        display_name=display_name.strip(),
    )
