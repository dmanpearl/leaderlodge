from datetime import date

import pytest

from leaderlodge.games.models import GameParticipantResult
from leaderlodge.leaderboards.streaks import (
    compute_streaks_from_results,
    streaks_by_player_from_participant_results,
)

Result = GameParticipantResult.Result


def test_compute_streaks_empty():
    streaks = compute_streaks_from_results([])
    assert streaks.longest == 0
    assert streaks.current == 0
    assert streaks.longest_start is None
    assert streaks.current_start is None


def test_compute_streaks_ties_continue_losses_break():
    streaks = compute_streaks_from_results(
        [Result.WIN, Result.TIE, Result.WIN, Result.LOSS, Result.WIN, Result.TIE]
    )
    assert streaks.longest == 3
    assert streaks.current == 2


def test_compute_streaks_trailing_loss_zeros_current():
    streaks = compute_streaks_from_results([Result.WIN, Result.WIN, Result.LOSS])
    assert streaks.longest == 2
    assert streaks.current == 0


def test_compute_streaks_played_breaks():
    streaks = compute_streaks_from_results([Result.WIN, Result.PLAYED, Result.WIN])
    assert streaks.longest == 1
    assert streaks.current == 1


def test_compute_streaks_dated_prefers_most_recent_max_run():
    from leaderlodge.leaderboards.streaks import compute_streaks_from_dated_results

    # Two runs of length 2; keep the later one as longest.
    streaks = compute_streaks_from_dated_results(
        [
            (Result.WIN, date(2026, 1, 1)),
            (Result.WIN, date(2026, 1, 2)),
            (Result.LOSS, date(2026, 1, 3)),
            (Result.WIN, date(2026, 2, 1)),
            (Result.TIE, date(2026, 2, 2)),
        ]
    )
    assert streaks.longest == 2
    assert streaks.longest_start == date(2026, 2, 1)
    assert streaks.longest_end == date(2026, 2, 2)
    assert streaks.current == 2
    assert streaks.current_start == date(2026, 2, 1)
    assert streaks.current_end == date(2026, 2, 2)


def test_streaks_by_player_orders_by_played_on_then_pk():
    def _row(player_id, played_on, game_pk, result):
        game = type(
            "Game",
            (),
            {"played_on": played_on, "pk": game_pk},
        )()
        return type(
            "ResultRow",
            (),
            {"player_id": player_id, "result": result, "game": game},
        )()

    # Same day: lower pk first, so W then L then W -> longest 1, current 1.
    results = [
        _row(1, date(2026, 1, 2), 30, Result.WIN),
        _row(1, date(2026, 1, 1), 10, Result.WIN),
        _row(1, date(2026, 1, 1), 20, Result.LOSS),
        _row(2, date(2026, 1, 1), 11, Result.TIE),
        _row(2, date(2026, 1, 1), 12, Result.TIE),
    ]
    by_player = streaks_by_player_from_participant_results(results)
    assert by_player[1].longest == 1
    assert by_player[1].current == 1
    assert by_player[2].longest == 2
    assert by_player[2].current == 2
