"""Shutout detection and filtering (game-type-specific labels live in the registry)."""

from __future__ import annotations

from collections.abc import Sequence

from leaderlodge.games.models import GameParticipantResult
from leaderlodge.games.registry import get_game_type, game_type_supports_shutout

Result = GameParticipantResult.Result


def is_shutout_game(
    game_type_code: str,
    results: Sequence[GameParticipantResult],
) -> bool:
    """
    True when the game type supports shutouts and exactly one side won while
    every opponent finished with zero points.
    """
    if not game_type_supports_shutout(game_type_code) or not results:
        return False

    get_game_type(game_type_code)
    winners = [row for row in results if row.result == Result.WIN]
    if len(winners) != 1:
        return False

    winner = winners[0]
    opponents = [row for row in results if row.player_id != winner.player_id]
    if not opponents:
        return False

    return all(row.score == 0 for row in opponents)


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
