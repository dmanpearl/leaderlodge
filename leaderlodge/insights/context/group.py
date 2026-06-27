"""Structured JSON context for group-level insight requests."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from leaderlodge.games.registry import ScoreDirection, get_game_type
from leaderlodge.leaderboards.hall_of_fame import (
    GRANULARITY_MONTH,
    build_hall_of_fame_grid,
    granularity_label,
    resolve_hall_of_fame_granularity,
)
from leaderlodge.leaderboards.period import LeaderboardPeriod
from leaderlodge.leaderboards.service import get_player_rankings

if TYPE_CHECKING:
    from leaderlodge.groups.models import Group

SCHEMA_VERSION = 1
SCOPE_LEADERBOARD = "leaderboard"
SCOPE_HALL_OF_FAME = "hall_of_fame"
TOP_RANKINGS_LIMIT = 15
MIN_RECOMMENDED_GAMES = 5


class GroupInsightContextError(ValueError):
    pass


def _round(value: float | None, places: int = 1) -> float | None:
    if value is None:
        return None
    return round(float(value), places)


def _ranking_row(row) -> dict[str, Any]:
    return {
        "rank": row.rank,
        "display_label": row.player.display_label,
        "rank_score": _round(row.rank_score, 1),
        "games_played": _round(row.games_played, 1),
        "wins": _round(row.wins, 1),
        "losses": _round(row.losses, 1),
        "win_pct": _round(row.win_pct, 1),
        "finish_points": _round(row.finish_points, 1),
    }


def _leaderboard_summary(ranked: list) -> dict[str, Any]:
    if not ranked:
        return {
            "player_count_ranked": 0,
            "total_weighted_games": 0,
            "leader": None,
            "runner_up": None,
            "leader_margin": None,
        }

    leader = ranked[0]
    runner_up = ranked[1] if len(ranked) > 1 else None
    margin = None
    if runner_up is not None:
        margin = _round(float(leader.rank_score) - float(runner_up.rank_score), 1)

    total_games = sum(float(row.games_played or 0) for row in ranked)
    return {
        "player_count_ranked": len(ranked),
        "total_weighted_games": _round(total_games, 1),
        "leader": _ranking_row(leader),
        "runner_up": _ranking_row(runner_up) if runner_up is not None else None,
        "leader_margin": margin,
    }


def _hall_of_fame_rows(group: Group, *, granularity: str) -> list[dict[str, Any]]:
    grid = build_hall_of_fame_grid(group, granularity=granularity)
    rows: list[dict[str, Any]] = []
    for row in grid.rows:
        cells: list[dict[str, Any]] = []
        for column, cell in zip(grid.columns, row.cells, strict=True):
            cells.append(
                {
                    "game_type_code": column.code,
                    "game_type_name": column.name,
                    "leader": cell.player_label or None,
                    "rank_score": _round(cell.rank_score, 1) if cell.rank_score is not None else None,
                }
            )
        rows.append(
            {
                "period_label": row.label,
                "year": row.period.year,
                "month": row.period.month,
                "leaders": cells,
            }
        )
    return rows


def build_group_insight_context(
    group: Group,
    *,
    scope: str,
    game_type_code: str | None = None,
    period: LeaderboardPeriod | None = None,
    granularity: str | None = None,
) -> dict[str, Any]:
    if scope == SCOPE_LEADERBOARD:
        if not game_type_code:
            raise GroupInsightContextError("Game type is required for leaderboard insights.")
        if period is None:
            period = LeaderboardPeriod.all_time()

        rankings = get_player_rankings(
            group,
            game_type_code=game_type_code,
            period=period,
        )
        ranked = [row for row in rankings if row.games_played > 0]
        if not ranked:
            raise GroupInsightContextError(
                "No ranked players for this leaderboard in the selected period."
            )

        game_type = get_game_type(game_type_code)
        total_games = sum(float(row.games_played or 0) for row in ranked)
        sparse = total_games < MIN_RECOMMENDED_GAMES

        return {
            "schema_version": SCHEMA_VERSION,
            "scope": SCOPE_LEADERBOARD,
            "group": {"id": group.pk, "name": group.name},
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
            "summary": _leaderboard_summary(ranked),
            "rankings": [_ranking_row(row) for row in ranked[:TOP_RANKINGS_LIMIT]],
            "data_quality": {
                "total_weighted_games": _round(total_games, 1),
                "min_recommended_for_trends": MIN_RECOMMENDED_GAMES,
                "sparse": sparse,
            },
        }

    if scope == SCOPE_HALL_OF_FAME:
        resolved_granularity = resolve_hall_of_fame_granularity(granularity or "")
        rows = _hall_of_fame_rows(group, granularity=resolved_granularity)
        if not rows:
            raise GroupInsightContextError("No Hall of Fame periods recorded for this group.")

        game_types = sorted(
            {
                leader["game_type_code"]
                for row in rows
                for leader in row["leaders"]
                if leader["leader"]
            }
        )
        return {
            "schema_version": SCHEMA_VERSION,
            "scope": SCOPE_HALL_OF_FAME,
            "group": {"id": group.pk, "name": group.name},
            "granularity": resolved_granularity,
            "granularity_label": granularity_label(resolved_granularity),
            "game_types": game_types,
            "period_leaders": rows,
            "data_quality": {
                "period_count": len(rows),
                "min_recommended_for_trends": 3
                if resolved_granularity == GRANULARITY_MONTH
                else 2,
                "sparse": len(rows) < 2,
            },
        }

    raise GroupInsightContextError("Unsupported insight scope.")
