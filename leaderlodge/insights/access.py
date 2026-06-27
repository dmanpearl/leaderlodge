"""Resolve group, player, and period for insight requests."""

from __future__ import annotations

from typing import TYPE_CHECKING

from leaderlodge.groups.models import Group
from leaderlodge.groups.services import visible_groups
from leaderlodge.leaderboards.period import (
    LeaderboardPeriod,
    available_leaderboard_periods,
    resolve_leaderboard_period,
)

if TYPE_CHECKING:
    from django.contrib.auth.models import AnonymousUser, User
    from django.http import HttpRequest

    from leaderlodge.games.models import Game
    from leaderlodge.groups.models import GroupPlayer


class InsightAccessError(PermissionError):
    pass


def _game_type_codes_for_group(group: Group) -> list[str]:
    from leaderlodge.games.models import Game

    return list(
        Game.objects.filter(group=group)
        .values_list("game_type_code", flat=True)
        .distinct()
        .order_by("game_type_code")
    )


def resolve_player_insight_target(
    request: HttpRequest,
    *,
    user: User | AnonymousUser,
    group_id: str,
    player_id: str,
    game_type_code: str,
    raw_year: str = "",
    raw_month: str = "",
) -> tuple[Group, GroupPlayer, str, LeaderboardPeriod]:
    groups = list(visible_groups(user).order_by("name"))
    group_ids = {str(group.pk) for group in groups}
    if group_id not in group_ids:
        raise InsightAccessError("Group not found.")

    group = next(item for item in groups if str(item.pk) == group_id)
    if game_type_code not in _game_type_codes_for_group(group):
        raise InsightAccessError("Game type not found for this group.")

    player = group.players.filter(pk=player_id).first()
    if player is None:
        raise InsightAccessError("Player not found in this group.")

    years, months_by_year = available_leaderboard_periods(group, game_type_code)
    period = resolve_leaderboard_period(
        raw_year=raw_year.strip(),
        raw_month=raw_month.strip(),
        available_years=years,
        months_by_year=months_by_year,
    )
    return group, player, game_type_code, period


def resolve_group_insight_target(
    request: HttpRequest,
    *,
    user: User | AnonymousUser,
    group_id: str,
    scope: str,
    game_type_code: str = "",
    raw_year: str = "",
    raw_month: str = "",
    granularity: str = "",
) -> tuple[Group, str, LeaderboardPeriod | None, str | None]:
    from leaderlodge.insights.context.group import SCOPE_HALL_OF_FAME, SCOPE_LEADERBOARD

    groups = list(visible_groups(user).order_by("name"))
    group_ids = {str(group.pk) for group in groups}
    if group_id not in group_ids:
        raise InsightAccessError("Group not found.")

    group = next(item for item in groups if str(item.pk) == group_id)
    resolved_scope = scope.strip()
    if resolved_scope not in (SCOPE_LEADERBOARD, SCOPE_HALL_OF_FAME):
        raise InsightAccessError("Invalid insight scope.")

    if resolved_scope == SCOPE_LEADERBOARD:
        if not game_type_code or game_type_code not in _game_type_codes_for_group(group):
            raise InsightAccessError("Game type not found for this group.")

        years, months_by_year = available_leaderboard_periods(group, game_type_code)
        period = resolve_leaderboard_period(
            raw_year=raw_year.strip(),
            raw_month=raw_month.strip(),
            available_years=years,
            months_by_year=months_by_year,
        )
        return group, resolved_scope, period, game_type_code

    return group, resolved_scope, None, None


def resolve_matchup_insight_target(
    request: HttpRequest,
    *,
    user: User | AnonymousUser,
    game_id: str,
) -> Game:
    from leaderlodge.games.models import Game
    from leaderlodge.groups.services import can_view_group

    game = (
        Game.objects.filter(pk=game_id)
        .select_related("group", "location")
        .first()
    )
    if game is None or not can_view_group(user, game.group):
        raise InsightAccessError("Game not found.")
    return game
