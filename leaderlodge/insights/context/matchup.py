"""Structured JSON context for matchup insight requests."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from leaderlodge.games.matchup import build_matchup_view
from leaderlodge.games.registry import ScoreDirection, get_game_type
from leaderlodge.insights.context.player import (
    InsightContextError,
    _placement_rows,
    _round,
)
from leaderlodge.leaderboards.period import LeaderboardPeriod
from leaderlodge.leaderboards.service import get_player_rank_detail

if TYPE_CHECKING:
    from leaderlodge.games.models import Game

SCHEMA_VERSION = 1
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
        "player": {"id": player.pk, "display_label": player.display_label},
        "ranking": {
            "rank": detail.ranking.rank,
            "rank_score": _round(detail.ranking.rank_score, 1),
            "games_played": _round(detail.ranking.games_played, 1),
            "wins": _round(detail.ranking.wins, 1),
            "losses": _round(detail.ranking.losses, 1),
            "win_pct": _round(detail.ranking.win_pct, 1),
            "loss_pct": _round(detail.ranking.loss_pct, 1),
        },
        "detail": {
            "podium_count": detail.podium_count,
            "podium_pct": _round(detail.podium_pct, 1),
            "average_field_size": _round(detail.average_field_size, 1),
            "game_count": detail.game_count,
        },
        "placements": _placement_rows(detail),
    }


def build_matchup_insight_context(game: Game) -> dict[str, Any]:
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
        "scope": "matchup",
        "group": {"id": game.group.pk, "name": game.group.name},
        "game": {
            "id": game.pk,
            "played_on": game.played_on.isoformat(),
            "location": game.location.name if game.location_id else None,
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
        "data_quality": {
            "player_count": len(players),
            "min_games_among_players": min_games,
            "min_recommended_for_trends": MIN_RECOMMENDED_GAMES,
            "sparse": sparse,
        },
    }
