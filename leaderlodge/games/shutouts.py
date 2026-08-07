"""Shutout detection and filtering (game-type-specific labels live in the registry)."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Literal

from leaderlodge.games.models import GameParticipantResult
from leaderlodge.games.registry import (
    game_type_shutout_config,
    game_type_supports_shutout,
)

Result = GameParticipantResult.Result

ShutoutTier = Literal["shutout", "skunk", "double_skunk"]


def _opponent_rows(
    results: Sequence[GameParticipantResult],
) -> list[GameParticipantResult] | None:
    """Return opponent rows when there is exactly one WIN; else None."""
    winners = [row for row in results if row.result == Result.WIN]
    if len(winners) != 1:
        return None

    winner = winners[0]
    opponents = [row for row in results if row.player_id != winner.player_id]
    if not opponents:
        return None
    return opponents


def shutout_tier(
    game_type_code: str,
    results: Sequence[GameParticipantResult],
) -> ShutoutTier | None:
    """
    Classify a shutout-capable game, or None when it is not a shutout.

    - Types without score ceilings: all opponents scored 0 ("shutout").
    - Types with max_opponent_score (e.g. Cribbage): all opponents at or under
      that score ("skunk"), or under double_max_opponent_score ("double_skunk").
    """
    if not game_type_supports_shutout(game_type_code) or not results:
        return None

    config = game_type_shutout_config(game_type_code)
    if config is None:
        return None

    opponents = _opponent_rows(results)
    if opponents is None:
        return None

    scores = [row.score for row in opponents]
    if any(score is None for score in scores):
        return None

    max_score = config.max_opponent_score
    if max_score is None:
        if all(score == 0 for score in scores):
            return "shutout"
        return None

    if not all(score <= max_score for score in scores):
        return None

    double_max = config.double_max_opponent_score
    if double_max is not None and all(score <= double_max for score in scores):
        return "double_skunk"
    return "skunk"


def is_shutout_game(
    game_type_code: str,
    results: Sequence[GameParticipantResult],
) -> bool:
    """
    True when the game type supports shutouts and the result set qualifies
    (zero-score shutout, skunk, or double-skunk per registry thresholds).
    """
    return shutout_tier(game_type_code, results) is not None


def is_double_skunk_game(
    game_type_code: str,
    results: Sequence[GameParticipantResult],
) -> bool:
    """True when every opponent finished at or under the double-skunk ceiling."""
    return shutout_tier(game_type_code, results) == "double_skunk"


def shutout_winner_result(
    game_type_code: str,
    results: Sequence[GameParticipantResult],
) -> GameParticipantResult | None:
    """Winning participant result for a shutout, or None."""
    if not is_shutout_game(game_type_code, results):
        return None
    return next(row for row in results if row.result == Result.WIN)


def shutout_game_ids(
    game_type_code: str,
    results: Sequence[GameParticipantResult],
) -> set[int]:
    """Game IDs that ended in a shutout."""
    by_game: dict[int, list[GameParticipantResult]] = {}
    for row in results:
        by_game.setdefault(row.game_id, []).append(row)

    return {
        game_id
        for game_id, game_results in by_game.items()
        if is_shutout_game(game_type_code, game_results)
    }


def shutout_counts_by_player(
    game_type_code: str,
    results: Sequence[GameParticipantResult],
) -> dict[int, float]:
    """
    Shutouts credited to the winning participant row only (team entity or solo).

    Individual members do not receive credit from team shutouts.
    """
    counts: dict[int, float] = {}
    by_game: dict[int, list[GameParticipantResult]] = {}
    for row in results:
        by_game.setdefault(row.game_id, []).append(row)

    for game_results in by_game.values():
        winner = shutout_winner_result(game_type_code, game_results)
        if winner is None:
            continue
        weight = winner.game.double_weight / winner.game.half_weight
        counts[winner.player_id] = counts.get(winner.player_id, 0.0) + weight
    return counts
