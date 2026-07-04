"""Team roster entities: find-or-create, labels, and credit expansion."""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Prefetch

from leaderlodge.groups.models import Group, GroupPlayer, GroupTeamMember

MAX_TEAM_SIZE = 2

PLAYER_TYPE_ALL = ""
PLAYER_TYPE_PEOPLE = "people"
PLAYER_TYPE_USER = GroupPlayer.PlayerType.USER
PLAYER_TYPE_GUEST = GroupPlayer.PlayerType.GUEST
PLAYER_TYPE_TEAM = GroupPlayer.PlayerType.TEAM

PLAYER_TYPE_CHOICES = (
    (PLAYER_TYPE_ALL, "All"),
    (PLAYER_TYPE_PEOPLE, "Users + Guests"),
    (PLAYER_TYPE_USER, "Users"),
    (PLAYER_TYPE_GUEST, "Guests"),
    (PLAYER_TYPE_TEAM, "Teams"),
)

VALID_PLAYER_TYPES = frozenset(
    value for value, _label in PLAYER_TYPE_CHOICES
) | frozenset({"all"})

PLAYER_TYPE_ICONS = {
    PLAYER_TYPE_USER: "bi-person-check",
    PLAYER_TYPE_GUEST: "bi-person",
    PLAYER_TYPE_TEAM: "bi-people",
}


def normalize_player_type(value: str) -> str:
    cleaned = (value or "").strip()
    if cleaned == "all":
        return PLAYER_TYPE_ALL
    if cleaned not in VALID_PLAYER_TYPES:
        return PLAYER_TYPE_ALL
    return cleaned


def player_type_filter_label(player_type: str) -> str:
    for value, label in PLAYER_TYPE_CHOICES:
        if value == player_type:
            return label if value else ""
    return ""


def player_type_icon(player: GroupPlayer) -> str:
    return PLAYER_TYPE_ICONS.get(player.player_type, "bi-person")


def matches_player_type(player: GroupPlayer, player_type: str) -> bool:
    if not player_type or player_type == "all":
        return True
    if player_type == PLAYER_TYPE_PEOPLE:
        return not player.is_team
    return player.player_type == player_type


def _sorted_members(members: list[GroupPlayer]) -> list[GroupPlayer]:
    return sorted(
        members,
        key=lambda player: (player.display_label.lower(), player.pk),
    )


def team_display_name(members: list[GroupPlayer]) -> str:
    return "+".join(player.display_label for player in _sorted_members(members))


def _member_key(members: list[GroupPlayer]) -> tuple[int, ...]:
    return tuple(sorted(player.pk for player in members))


def validate_side_members(members: list[GroupPlayer], *, group: Group) -> None:
    if not members:
        raise ValidationError("Each side needs at least one player.")
    if len(members) > MAX_TEAM_SIZE:
        raise ValidationError(f"Teams may have at most {MAX_TEAM_SIZE} players.")
    member_ids = [player.pk for player in members]
    if len(member_ids) != len(set(member_ids)):
        raise ValidationError("A player cannot appear twice on the same side.")
    for player in members:
        if player.group_id != group.pk:
            raise ValidationError("All players must belong to the selected group.")
        if player.is_team:
            raise ValidationError("A team cannot be a member of another team.")


def validate_sides_no_shared_players(sides: list[list[GroupPlayer]]) -> None:
    seen: set[int] = set()
    for members in sides:
        for player in members:
            if player.pk in seen:
                raise ValidationError(
                    f"{player.display_label} cannot play on more than one side."
                )
            seen.add(player.pk)


@transaction.atomic
def resolve_side_player(*, group: Group, members: list[GroupPlayer]) -> GroupPlayer:
    """Return the solo player or find-or-create team GroupPlayer for members."""
    validate_side_members(members, group=group)
    if len(members) == 1:
        return members[0]

    ordered = _sorted_members(members)
    member_key = _member_key(ordered)
    label = team_display_name(ordered)

    existing_teams = (
        GroupPlayer.objects.filter(group=group, is_team=True)
        .prefetch_related(
            Prefetch(
                "team_members",
                queryset=GroupTeamMember.objects.select_related("member"),
            )
        )
        .order_by("pk")
    )
    for team in existing_teams:
        team_member_key = tuple(
            sorted(link.member_id for link in team.team_members.all())
        )
        if team_member_key == member_key:
            if team.display_name != label:
                team.display_name = label
                team.save(update_fields=["display_name"])
            return team

    team = GroupPlayer.objects.create(
        group=group,
        display_name=label,
        is_team=True,
        linked_user=None,
    )
    GroupTeamMember.objects.bulk_create(
        [GroupTeamMember(team=team, member=member) for member in ordered]
    )
    return team


def team_member_players(team: GroupPlayer) -> list[GroupPlayer]:
    if not team.is_team:
        return []
    links = team.team_members.select_related("member", "member__linked_user").order_by(
        "pk"
    )
    members = [link.member for link in links]
    return _sorted_members(members)


def credit_players_for_result(player: GroupPlayer) -> list[GroupPlayer]:
    """People who receive individual credit for a participant result."""
    if player.is_team:
        return team_member_players(player)
    return [player]


def leaderboard_credit_players(player: GroupPlayer) -> list[GroupPlayer]:
    """Leaderboard rows credited for a participant (team entity plus members)."""
    if player.is_team:
        return [player, *team_member_players(player)]
    return [player]


def vesting_games_played_for_player(
    player: GroupPlayer,
    games_played_by_id: dict[int, float],
) -> float:
    """
    Weighted games used for vesting.

    People use their own total. Teams use the member with the fewest games.
    """
    own = float(games_played_by_id.get(player.pk, 0.0))
    if not player.is_team:
        return own
    members = team_member_players(player)
    member_counts = [
        float(games_played_by_id[member.pk])
        for member in members
        if member.pk in games_played_by_id
    ]
    if not member_counts:
        return own
    return min(member_counts)


def results_queryset_for_player_credit(player: GroupPlayer):
    """Filter GameParticipantResult rows that credit this player."""
    from leaderlodge.games.models import GameParticipantResult

    if player.is_team:
        return GameParticipantResult.objects.filter(player=player)

    team_ids = GroupTeamMember.objects.filter(member=player).values_list(
        "team_id", flat=True
    )
    return GameParticipantResult.objects.filter(player=player) | (
        GameParticipantResult.objects.filter(player_id__in=team_ids)
    )
