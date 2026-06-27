from __future__ import annotations

from leaderlodge.games.registry import get_game_type
from leaderlodge.groups.models import Group, GroupPlayer
from leaderlodge.leaderboards.period import LeaderboardPeriod
from leaderlodge.leaderboards.service import get_player_rank_detail, get_player_rankings


def _ranking_row(row) -> dict:
    return {
        "player_id": row.player.pk,
        "display_label": row.player.display_label,
        "rank": row.rank,
        "rank_score": round(row.rank_score, 2),
        "games_played": round(row.games_played, 2),
        "wins": round(row.wins, 2),
        "win_pct": round(row.win_pct, 1),
    }


def query_leaderboard(
    group: Group,
    *,
    game_type_code: str,
    period: LeaderboardPeriod | None = None,
    game_size: int | None = None,
    limit: int = 10,
) -> dict:
    if period is None:
        period = LeaderboardPeriod.all_time()

    game_type = get_game_type(game_type_code)
    rankings = get_player_rankings(
        group,
        game_type_code=game_type_code,
        period=period,
        game_size=game_size,
    )
    return {
        "game_type_code": game_type_code,
        "game_type_name": game_type.name,
        "game_size": game_size,
        "period": period.query_params() or {"all_time": True},
        "rankings": [_ranking_row(row) for row in rankings[:limit]],
    }


def query_player_detail(
    group: Group,
    *,
    player_id: int,
    game_type_code: str,
    period: LeaderboardPeriod | None = None,
    game_size: int | None = None,
) -> dict:
    if period is None:
        period = LeaderboardPeriod.all_time()

    player = group.players.filter(pk=player_id).select_related("linked_user").first()
    if player is None:
        return {"error": "Player not found in this group."}

    detail = get_player_rank_detail(
        group,
        player,
        game_type_code=game_type_code,
        period=period,
        game_size=game_size,
    )
    if detail is None:
        return {
            "player_id": player.pk,
            "display_label": player.display_label,
            "game_type_code": game_type_code,
            "has_games": False,
        }

    game_type = get_game_type(game_type_code)
    return {
        "player_id": player.pk,
        "display_label": player.display_label,
        "game_type_code": game_type_code,
        "game_type_name": game_type.name,
        "game_size": game_size,
        "period": period.query_params() or {"all_time": True},
        "rank": detail.ranking.rank,
        "rank_score": round(detail.ranking.rank_score, 2),
        "games_played": round(detail.ranking.games_played, 2),
        "wins": round(detail.ranking.wins, 2),
        "win_pct": round(detail.ranking.win_pct, 1),
        "average_field_size": round(detail.average_field_size, 1),
        "placements": [
            {
                "placement": item.placement,
                "label": item.label,
                "weighted_count": round(item.weighted_count, 2),
                "count_pct": round(item.count_pct, 1),
            }
            for item in detail.placements
        ],
        "supports_loser": game_type.supports_loser,
    }


def list_game_types(group: Group) -> dict:
    from leaderlodge.games.models import Game
    from leaderlodge.games.registry import get_game_type

    codes = list(
        Game.objects.filter(group=group)
        .values_list("game_type_code", flat=True)
        .distinct()
        .order_by("game_type_code")
    )
    return {
        "group_id": group.pk,
        "group_name": group.name,
        "game_types": [
            {
                "code": code,
                "name": get_game_type(code).name,
            }
            for code in codes
        ],
    }
