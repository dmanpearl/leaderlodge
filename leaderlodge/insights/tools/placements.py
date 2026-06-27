from __future__ import annotations

from django.db.models import Sum

from leaderlodge.games.models import GameParticipantResult
from leaderlodge.games.registry import get_game_type
from leaderlodge.games.standings import standings_weight_expression
from leaderlodge.groups.models import Group, GroupPlayer
from leaderlodge.leaderboards.period import LeaderboardPeriod, filter_results_by_period
from leaderlodge.leaderboards.ranking import ordinal_place_label


def query_placement_leaders(
    group: Group,
    *,
    game_type_code: str,
    placement: int,
    period: LeaderboardPeriod | None = None,
    game_size: int | None = None,
    limit: int = 10,
) -> dict:
    if period is None:
        period = LeaderboardPeriod.all_time()

    game_type = get_game_type(game_type_code)
    weight = standings_weight_expression()
    results_qs = GameParticipantResult.objects.filter(
        game__group=group,
        game__game_type_code=game_type_code,
        placement=placement,
    )
    if game_size is not None:
        results_qs = results_qs.filter(game__player_count=game_size)
    results_qs = filter_results_by_period(results_qs, period)

    rows = list(
        results_qs.values("player_id")
        .annotate(weighted_count=Sum(weight))
        .order_by("-weighted_count", "player_id")[:limit]
    )
    player_ids = [row["player_id"] for row in rows]
    players_by_id = {
        player.pk: player
        for player in GroupPlayer.objects.filter(pk__in=player_ids).select_related(
            "linked_user"
        )
    }

    leaders = []
    for row in rows:
        player = players_by_id.get(row["player_id"])
        if player is None:
            continue
        leaders.append(
            {
                "player_id": player.pk,
                "display_label": player.display_label,
                "weighted_count": float(row["weighted_count"] or 0),
            }
        )

    return {
        "game_type_code": game_type_code,
        "game_type_name": game_type.name,
        "placement": placement,
        "placement_label": ordinal_place_label(placement),
        "game_size": game_size,
        "period": period.query_params() or {"all_time": True},
        "leaders": leaders,
    }
