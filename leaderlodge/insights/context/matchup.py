"""Structured JSON context for game-set insight requests (matchup + game detail)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from leaderlodge.games.matchup import build_matchup_view
from leaderlodge.games.registry import ScoreDirection, get_game_type
from leaderlodge.insights.context.player import InsightContextError, _round
from leaderlodge.leaderboards.period import LeaderboardPeriod
from leaderlodge.leaderboards.service import get_player_rank_detail

if TYPE_CHECKING:
    from leaderlodge.games.models import Game

SCHEMA_VERSION = 3
MIN_RECOMMENDED_GAMES = 3


class MatchupInsightContextError(ValueError):
    pass


def _matchup_table_rows(matchup) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in matchup.rows:
        cells: list[dict[str, Any]] = []
        for column, cell in zip(matchup.players, row.cells, strict=True):
            entry: dict[str, Any] = {
                "display_label": column.player.display_label,
                "value": cell.display,
            }
            if cell.change != "none":
                entry["change"] = cell.change
            if column.standing_highlight:
                entry["standing_highlight"] = column.standing_highlight
            cells.append(entry)
        rows.append({"label": row.label, "cells": cells})
    return rows


def _player_summary(
    group,
    player,
    *,
    game_type_code: str,
) -> dict[str, Any]:
    detail = get_player_rank_detail(
        group,
        player,
        game_type_code=game_type_code,
        period=LeaderboardPeriod.all_time(),
    )
    if detail is None:
        raise InsightContextError("No recorded games for this player.")

    return {
        "display_label": player.display_label,
        "ranking": {
            "rank": detail.ranking.rank,
            "rank_score": _round(detail.ranking.rank_score, 1),
            "games_played": _round(detail.ranking.games_played, 1),
            "wins": _round(detail.ranking.wins, 1),
            "win_pct": _round(detail.ranking.win_pct, 1),
        },
    }


def _ranked_entries(
    summaries: list[dict[str, Any]],
    *,
    field: str,
    higher_is_better: bool,
) -> list[dict[str, Any]]:
    sortable: list[tuple[float, str, dict[str, Any]]] = []
    for summary in summaries:
        value = summary["ranking"].get(field)
        if value is None:
            continue
        sortable.append((float(value), summary["display_label"], summary))

    sortable.sort(key=lambda item: item[0], reverse=higher_is_better)
    entries: list[dict[str, Any]] = []
    for index, (value, label, _summary) in enumerate(sortable, start=1):
        entries.append(
            {
                "rank": index,
                "display_label": label,
                field: _round(value, 1),
            }
        )
    return entries


def _ranked_by_leaderboard_rank(
    summaries: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    sortable: list[tuple[float, str, int | None]] = []
    for summary in summaries:
        rank = summary["ranking"].get("rank")
        if rank is None:
            continue
        sortable.append((float(rank), summary["display_label"], rank))

    sortable.sort(key=lambda item: item[0])
    return [
        {
            "rank": index,
            "display_label": label,
            "leaderboard_rank": board_rank,
        }
        for index, (_sort_key, label, board_rank) in enumerate(sortable, start=1)
    ]


def _computed_rankings(summaries: list[dict[str, Any]]) -> dict[str, Any]:
    by_games = _ranked_entries(summaries, field="games_played", higher_is_better=True)
    by_score = _ranked_entries(summaries, field="rank_score", higher_is_better=True)
    by_wins = _ranked_entries(summaries, field="wins", higher_is_better=True)
    by_board_rank = _ranked_by_leaderboard_rank(summaries)

    leaders: dict[str, str | None] = {
        "most_games": by_games[0]["display_label"] if by_games else None,
        "highest_rank_score": by_score[0]["display_label"] if by_score else None,
        "most_wins": by_wins[0]["display_label"] if by_wins else None,
        "best_leaderboard_rank": (
            by_board_rank[0]["display_label"] if by_board_rank else None
        ),
    }

    return {
        "by_games_played": by_games,
        "by_rank_score": by_score,
        "by_wins": by_wins,
        "by_leaderboard_rank": by_board_rank,
        "leaders": leaders,
    }


def build_matchup_insight_context(game: Game) -> dict[str, Any]:
    """Build insight JSON for all players in one game (matchup + game detail)."""
    matchup = build_matchup_view(game)
    if not matchup.players:
        raise MatchupInsightContextError("This game has no participants.")

    game_type = get_game_type(game.game_type_code)
    players = [column.player for column in matchup.players]
    player_summaries: list[dict[str, Any]] = []
    for player in players:
        player_summaries.append(
            _player_summary(
                game.group,
                player,
                game_type_code=game.game_type_code,
            )
        )

    min_games = min(
        int(summary["ranking"]["games_played"] or 0) for summary in player_summaries
    )
    sparse = min_games < MIN_RECOMMENDED_GAMES

    return {
        "schema_version": SCHEMA_VERSION,
        "scope": "game_set",
        "group": {"id": game.group.pk, "name": game.group.name},
        "game": {
            "id": game.pk,
            "played_on": game.played_on.isoformat(),
            "location": game.location.name if game.location_id else None,
            "location_city": (
                (game.location.city or None) if game.location_id else None
            ),
            "location_state": (
                (game.location.state or None) if game.location_id else None
            ),
            "is_double": game.double_weight == 2,
            "is_half": game.half_weight == 2,
        },
        "game_type": {
            "code": game_type.code,
            "name": game_type.name,
            "score_direction": (
                "low_wins"
                if game_type.score_direction == ScoreDirection.LOW_WINS
                else "high_wins"
            ),
        },
        "players": [
            {
                "display_label": column.player.display_label,
                "standing_highlight": column.standing_highlight or None,
            }
            for column in matchup.players
        ],
        "matchup_table": _matchup_table_rows(matchup),
        "player_summaries": player_summaries,
        "computed_rankings": _computed_rankings(player_summaries),
        "data_quality": {
            "player_count": len(players),
            "min_games_among_players": min_games,
            "min_recommended_for_trends": MIN_RECOMMENDED_GAMES,
            "sparse": sparse,
        },
    }
