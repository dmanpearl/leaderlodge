from django.contrib.auth.models import AbstractBaseUser

from leaderlodge.groups.models import Group, GroupMembership, GroupPlayer

Role = GroupMembership.Role


def get_membership(
    user: AbstractBaseUser | None, group: Group
) -> GroupMembership | None:
    if user is None or not user.is_authenticated:
        return None
    return GroupMembership.objects.filter(group=group, user=user).first()


def can_manage_members(membership: GroupMembership | None) -> bool:
    if membership is None:
        return False
    return membership.role in (Role.OWNER, Role.EDITOR)


def owner_count(group: Group) -> int:
    return GroupMembership.objects.filter(group=group, role=Role.OWNER).count()


def is_last_owner(membership: GroupMembership) -> bool:
    return membership.role == Role.OWNER and owner_count(membership.group) <= 1


def assignable_roles(actor: GroupMembership, target: GroupMembership) -> list[str]:
    if not can_manage_members(actor):
        return []
    if actor.role == Role.EDITOR and target.role == Role.OWNER:
        return []
    if is_last_owner(target):
        return [Role.OWNER]
    roles = [Role.MEMBER, Role.EDITOR]
    if actor.role == Role.OWNER:
        roles.append(Role.OWNER)
    return roles


def role_choice_options(
    actor: GroupMembership, target: GroupMembership
) -> list[tuple[str, str]]:
    allowed = assignable_roles(actor, target)
    return [(value, label) for value, label in Role.choices if value in allowed]


def can_set_membership_role(
    actor: GroupMembership,
    target: GroupMembership,
    new_role: str,
) -> bool:
    if new_role not in Role.values:
        return False
    return new_role in assignable_roles(actor, target)


def can_remove_membership(actor: GroupMembership, target: GroupMembership) -> bool:
    if not can_manage_members(actor):
        return False
    if is_last_owner(target):
        return False
    if actor.role == Role.EDITOR and target.role == Role.OWNER:
        return False
    return True


def player_has_games(player: GroupPlayer) -> bool:
    return player.game_results.exists()


def roster_remove_state(
    actor: GroupMembership | None,
    player: GroupPlayer,
    group: Group,
) -> dict:
    """Remove-button state for a roster row (member or guest player)."""
    hidden = {
        "show_remove": False,
        "can_remove": False,
        "remove_url_name": "",
        "remove_target_pk": None,
        "disabled_reason": "",
    }
    if not can_manage_members(actor):
        return hidden
    if player.group_id != group.pk or not player.is_active:
        return hidden

    if player.linked_user_id:
        membership = GroupMembership.objects.filter(
            group=group,
            user_id=player.linked_user_id,
        ).first()
        if membership is not None:
            if can_remove_membership(actor, membership):
                return {
                    "show_remove": True,
                    "can_remove": True,
                    "remove_url_name": "groups:member_remove",
                    "remove_target_pk": membership.pk,
                    "disabled_reason": "",
                }
            return hidden

    if player_has_games(player):
        return {
            "show_remove": True,
            "can_remove": False,
            "remove_url_name": "",
            "remove_target_pk": None,
            "disabled_reason": (
                "Cannot remove from group - this player has recorded games."
            ),
        }

    return {
        "show_remove": True,
        "can_remove": True,
        "remove_url_name": "groups:player_remove",
        "remove_target_pk": player.pk,
        "disabled_reason": "",
    }


def can_remove_roster_player(
    actor: GroupMembership | None,
    player: GroupPlayer,
    group: Group,
) -> bool:
    state = roster_remove_state(actor, player, group)
    return state["can_remove"] and state["remove_url_name"] == "groups:player_remove"


def can_combine_players(
    user: AbstractBaseUser | None,
    group: Group,
) -> bool:
    if user is None or not user.is_authenticated:
        return False
    if group.is_demo:
        return bool(user.is_staff or user.is_superuser)
    if user.is_staff or user.is_superuser:
        from leaderlodge.groups.services import user_is_member

        return user_is_member(user, group)
    membership = get_membership(user, group)
    return membership is not None and membership.role == Role.OWNER


def can_invite_roster_player(
    actor: GroupMembership | None,
    player: GroupPlayer,
    group: Group,
) -> bool:
    if not can_manage_members(actor):
        return False
    if player.group_id != group.pk or not player.is_active:
        return False
    return player.linked_user_id is None
