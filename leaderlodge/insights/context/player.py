"""Structured JSON context for player insight requests."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from leaderlodge.games.registry import ScoreDirection, get_game_type
from leaderlodge.leaderboards.period import LeaderboardPeriod
from leaderlodge.leaderboards.service import (
    PlayerRankDetail,
    get_player_rank_detail,
    get_player_rankings,
)

if TYPE_CHECKING:
    from leaderlodge.groups.models import Group, GroupPlayer

SCHEMA_VERSION = 1
MIN_RECOMMENDED_GAMES = 5


class InsightContextError(ValueError):
    pass


def _round(value: float | None, places: int = 1) -> float | None:
    if value is None:
        return None
    return round(float(value), places)


def _score_highlight(highlight) -> dict[str, Any] | None:
    if highlight is None:
        return None
    return {
        "score": highlight.score,
        "played_on": highlight.played_on.isoformat(),
    }


def _placement_rows(detail: PlayerRankDetail) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in detail.placements:
        rows.append(
            {
                "label": row.label,
                "placement": row.placement,
                "weighted_count": _round(row.weighted_count, 1),
                "count_pct": _round(row.count_pct, 1),
                "avg_finish_points": _round(row.avg_finish_points, 1),
                "field_sizes": [
                    {
                        "player_count": size.player_count,
                        "weighted_count": _round(size.weighted_count, 1),
                        "count_pct": _round(size.count_pct, 1),
                    }
                    for size in row.field_sizes
                ],
            }
        )
    return rows


def _group_comparison(
    group: Group,
    *,
    player: GroupPlayer,
    game_type_code: str,
    period: LeaderboardPeriod,
    player_rank_score: float,
) -> dict[str, Any]:
    rankings = get_player_rankings(
        group,
        game_type_code=game_type_code,
        period=period,
    )
    ranked = [row for row in rankings if row.games_played > 0]
    leader = ranked[0] if ranked else None
    gap = None
    if leader is not None and leader.player.pk != player.pk:
        gap = _round(leader.rank_score - player_rank_score, 1)
    return {
        "player_count_ranked": len(ranked),
        "leader": (
            {
                "display_label": leader.player.display_label,
                "rank_score": _round(leader.rank_score, 1),
            }
            if leader is not None
            else None
        ),
        "rank_score_gap_to_leader": gap,
    }


def build_player_insight_context(
    group: Group,
    player: GroupPlayer,
    *,
    game_type_code: str,
    period: LeaderboardPeriod | None = None,
) -> dict[str, Any]:
    if period is None:
        period = LeaderboardPeriod.all_time()

    detail = get_player_rank_detail(
        group,
        player,
        game_type_code=game_type_code,
        period=period,
    )
    if detail is None:
        raise InsightContextError(
            "No recorded games for this player in the selected period."
        )

    game_type = get_game_type(game_type_code)
    games_in_period = int(detail.ranking.games_played or 0)
    sparse = games_in_period < MIN_RECOMMENDED_GAMES

    return {
        "schema_version": SCHEMA_VERSION,
        "group": {"id": group.pk, "name": group.name},
        "player": {"id": player.pk, "display_label": player.display_label},
        "game_type": {
            "code": game_type.code,
            "name": game_type.name,
            "score_direction": (
                "low_wins"
                if game_type.score_direction == ScoreDirection.LOW_WINS
                else "high_wins"
            ),
        },
        "period": {
            "label": period.display_label(),
            "year": period.year,
            "month": period.month,
        },
        "ranking": {
            "rank": detail.ranking.rank,
            "rank_score": _round(detail.ranking.rank_score, 1),
            "games_played": _round(detail.ranking.games_played, 1),
            "wins": _round(detail.ranking.wins, 1),
            "losses": _round(detail.ranking.losses, 1),
            "win_pct": _round(detail.ranking.win_pct, 1),
            "loss_pct": _round(detail.ranking.loss_pct, 1),
            "finish_points": _round(detail.ranking.finish_points, 1),
        },
        "detail": {
            "raw_rank_score": _round(detail.raw_rank_score, 1),
            "vesting_multiplier": _round(detail.vesting_multiplier, 1),
            "podium_count": detail.podium_count,
            "podium_pct": _round(detail.podium_pct, 1),
            "average_field_size": _round(detail.average_field_size, 1),
            "average_score": _round(detail.average_score, 1),
            "best_score": _score_highlight(detail.best_score),
            "worst_score": _score_highlight(detail.worst_score),
            "date_range_label": detail.date_range_label,
            "game_count": detail.game_count,
            "tie_count": detail.tie_count,
            "double_game_count": detail.double_game_count,
            "half_game_count": detail.half_game_count,
        },
        "placements": _placement_rows(detail),
        "group_comparison": _group_comparison(
            group,
            player=player,
            game_type_code=game_type_code,
            period=period,
            player_rank_score=float(detail.ranking.rank_score),
        ),
        "data_quality": {
            "games_in_period": games_in_period,
            "min_recommended_for_trends": MIN_RECOMMENDED_GAMES,
            "sparse": sparse,
        },
    }
