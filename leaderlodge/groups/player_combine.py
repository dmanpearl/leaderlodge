"""Merge two roster players in the same group into one."""

from __future__ import annotations

from dataclasses import dataclass

from django.db import transaction

from leaderlodge.games.models import GameParticipantResult
from leaderlodge.groups.models import GroupInvite, GroupPlayer, GroupTeamMember
from leaderlodge.groups.names import format_user_display_name


@dataclass(frozen=True)
class CombinePlayersPreview:
    keeper: GroupPlayer
    source: GroupPlayer
    games_moved: int
    games_dropped: int
    invites_moved: int
    team_links_moved: int
    insight_logs_moved: int


def players_shared_a_game(*, keeper: GroupPlayer, source: GroupPlayer) -> bool:
    keeper_game_ids = keeper.game_results.values_list("game_id", flat=True)
    if not keeper_game_ids:
        return False
    return source.game_results.filter(game_id__in=keeper_game_ids).exists()


def combinable_source_players(*, group, keeper: GroupPlayer):
    keeper_game_ids = keeper.game_results.values_list("game_id", flat=True)
    blocked_player_ids = (
        GameParticipantResult.objects.filter(
            game_id__in=keeper_game_ids,
        )
        .exclude(player_id=keeper.pk)
        .values_list("player_id", flat=True)
    )
    return (
        group.players.filter(is_active=True, is_team=False)
        .exclude(pk=keeper.pk)
        .exclude(pk__in=blocked_player_ids)
        .select_related("linked_user")
        .order_by("display_name")
    )


def validate_combine_players(*, keeper: GroupPlayer, source: GroupPlayer) -> None:
    if keeper.pk == source.pk:
        raise ValueError("Choose two different players to combine.")
    if keeper.group_id != source.group_id:
        raise ValueError("Players must be in the same group.")
    if keeper.is_team or source.is_team:
        raise ValueError("Teams cannot be combined with other players.")
    if keeper.linked_user_id and source.linked_user_id:
        raise ValueError("Cannot combine two players that each have a linked account.")
    if not keeper.is_active or not source.is_active:
        raise ValueError("Only active roster players can be combined.")
    if players_shared_a_game(keeper=keeper, source=source):
        raise ValueError("Cannot combine two players who have played in the same game.")


def preview_combine_players(
    *, keeper: GroupPlayer, source: GroupPlayer
) -> CombinePlayersPreview:
    validate_combine_players(keeper=keeper, source=source)
    keeper_game_ids = set(keeper.game_results.values_list("game_id", flat=True))
    source_game_ids = list(source.game_results.values_list("game_id", flat=True))
    games_moved = sum(
        1 for game_id in source_game_ids if game_id not in keeper_game_ids
    )
    games_dropped = len(source_game_ids) - games_moved
    invites_moved = GroupInvite.objects.filter(guest_player=source).count()
    team_links = list(
        GroupTeamMember.objects.filter(member=source).values_list("team_id", flat=True)
    )
    keeper_team_ids = set(
        GroupTeamMember.objects.filter(member=keeper).values_list("team_id", flat=True)
    )
    team_links_moved = sum(
        1 for team_id in team_links if team_id not in keeper_team_ids
    )
    from leaderlodge.insights.models import InsightLog

    insight_logs_moved = InsightLog.objects.filter(player=source).count()
    return CombinePlayersPreview(
        keeper=keeper,
        source=source,
        games_moved=games_moved,
        games_dropped=games_dropped,
        invites_moved=invites_moved,
        team_links_moved=team_links_moved,
        insight_logs_moved=insight_logs_moved,
    )


@transaction.atomic
def combine_players(
    *, keeper: GroupPlayer, source: GroupPlayer
) -> CombinePlayersPreview:
    validate_combine_players(keeper=keeper, source=source)
    keeper = GroupPlayer.objects.select_for_update().get(pk=keeper.pk)
    source = GroupPlayer.objects.select_for_update().get(pk=source.pk)
    validate_combine_players(keeper=keeper, source=source)
    preview = preview_combine_players(keeper=keeper, source=source)

    keeper_game_ids = set(keeper.game_results.values_list("game_id", flat=True))
    for result in list(source.game_results.select_related("game")):
        if result.game_id in keeper_game_ids:
            result.delete()
        else:
            result.player = keeper
            result.save(update_fields=["player"])
            keeper_game_ids.add(result.game_id)

    GroupInvite.objects.filter(guest_player=source).update(guest_player=keeper)

    for team_link in list(GroupTeamMember.objects.filter(member=source)):
        if GroupTeamMember.objects.filter(
            team_id=team_link.team_id, member=keeper
        ).exists():
            team_link.delete()
        else:
            team_link.member = keeper
            team_link.save(update_fields=["member"])

    from leaderlodge.insights.models import InsightLog

    InsightLog.objects.filter(player=source).update(player=keeper)

    keeper_updates: list[str] = []
    if source.linked_user_id and not keeper.linked_user_id:
        keeper.linked_user = source.linked_user
        keeper_updates.append("linked_user")
        keeper.display_name = format_user_display_name(source.linked_user)
        keeper_updates.append("display_name")
    if source.is_active and not keeper.is_active:
        keeper.is_active = True
        keeper_updates.append("is_active")
    if keeper.hide_from_game_list and not source.hide_from_game_list:
        keeper.hide_from_game_list = False
        keeper_updates.append("hide_from_game_list")
    if keeper_updates:
        keeper.save(update_fields=keeper_updates)

    source.delete()
    return preview
