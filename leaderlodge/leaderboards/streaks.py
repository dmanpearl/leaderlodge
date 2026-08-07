"""Streak computation: WIN/TIE continue a streak; LOSS (and other non-continues) break it."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date

from leaderlodge.games.models import GameParticipantResult

Result = GameParticipantResult.Result

# Continues a streak; everything else (LOSS, PLAYED, unknown) breaks it.
_STREAK_CONTINUES = frozenset({Result.WIN, Result.TIE})


@dataclass(frozen=True)
class PlayerStreaks:
    longest: int = 0
    current: int = 0
    longest_start: date | None = None
    longest_end: date | None = None
    current_start: date | None = None
    current_end: date | None = None


def streak_continues(result: str) -> bool:
    return result in _STREAK_CONTINUES


def compute_streaks_from_results(results: Sequence[str]) -> PlayerStreaks:
    """
    Compute longest and current streak from a chronological result sequence.

    Current is the trailing run at the end of the sequence (0 if empty or
    the last result does not continue the streak). Dates are omitted.
    """
    return compute_streaks_from_dated_results(
        [(result, date.min) for result in results]
    )


def compute_streaks_from_dated_results(
    events: Sequence[tuple[str, date]],
) -> PlayerStreaks:
    """
    Compute longest and current streak with start/end dates.

    When multiple runs share the same max length, the most recent run is kept
    as longest (run length >= current max updates the span).
    """
    longest = 0
    longest_start: date | None = None
    longest_end: date | None = None
    run = 0
    run_start: date | None = None
    last_continue: date | None = None

    for result, played_on in events:
        if streak_continues(result):
            if run == 0:
                run_start = played_on
            run += 1
            last_continue = played_on
            if run >= longest:
                longest = run
                longest_start = run_start
                longest_end = played_on
        else:
            run = 0
            run_start = None

    if run > 0:
        return PlayerStreaks(
            longest=longest,
            current=run,
            longest_start=longest_start,
            longest_end=longest_end,
            current_start=run_start,
            current_end=last_continue,
        )
    return PlayerStreaks(
        longest=longest,
        current=0,
        longest_start=longest_start,
        longest_end=longest_end,
    )


def streaks_by_player_from_participant_results(
    results: Iterable[GameParticipantResult],
) -> dict[int, PlayerStreaks]:
    """
    Streaks keyed by participant player_id (team entity or solo side).

    Does not expand team credit to individual members. Results for the same
    player are ordered by (played_on, game.pk).
    """
    by_player: dict[int, list[tuple[date, int, str]]] = defaultdict(list)
    for row in results:
        game = row.game
        by_player[row.player_id].append((game.played_on, game.pk, row.result))

    out: dict[int, PlayerStreaks] = {}
    for player_id, events in by_player.items():
        events.sort(key=lambda item: (item[0], item[1]))
        out[player_id] = compute_streaks_from_dated_results(
            [(result, played_on) for played_on, _pk, result in events]
        )
    return out
