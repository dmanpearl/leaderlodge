import pytest
from django.core.exceptions import ValidationError

from leaderlodge.games.models import GameParticipantResult
from leaderlodge.games.scoring import (
    assign_results_from_scores,
    evaluate_results_from_rows,
    player_count_is_valid,
)

Result = GameParticipantResult.Result


class FakePlayer:
    def __init__(self, pk):
        self.pk = pk


def _rows(scores):
    return [
        {
            "player": FakePlayer(i),
            "score": score,
            "result": Result.PLAYED,
        }
        for i, score in enumerate(scores)
    ]


def test_unique_high_score_wins():
    rows = _rows([30, 20])
    evaluation = evaluate_results_from_rows(rows, "dominos")
    assert evaluation.win_pks == {0}
    assert evaluation.tie_pks == set()
    assert evaluation.loss_pks == set()


def test_tied_high_scores_are_tie():
    rows = _rows([20, 20])
    evaluation = evaluate_results_from_rows(rows, "dominos")
    assert evaluation.win_pks == set()
    assert evaluation.tie_pks == {0, 1}


def test_tied_low_scores_are_both_losses():
    rows = _rows([30, 20, 20])
    evaluation = evaluate_results_from_rows(rows, "progressiverummy")
    assert evaluation.win_pks == {0}
    assert evaluation.tie_pks == set()
    assert evaluation.loss_pks == {1, 2}


def test_all_same_score_is_tie_without_loser():
    rows = _rows([25, 25, 25])
    evaluation = evaluate_results_from_rows(rows, "progressiverummy")
    assert evaluation.tie_pks == {0, 1, 2}
    assert evaluation.loss_pks == set()


def test_assign_results_from_scores():
    rows = _rows([10, 20])
    assign_results_from_scores(rows, "dominos")
    assert rows[1]["result"] == Result.WIN
    assert rows[0]["result"] == Result.PLAYED


def test_player_count_is_valid():
    assert player_count_is_valid(2, "dominos") is True
    assert player_count_is_valid(1, "dominos") is False


def test_assign_rejects_no_top_result():
    rows = []
    with pytest.raises(ValidationError):
        assign_results_from_scores(rows, "dominos")
