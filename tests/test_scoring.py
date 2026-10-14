import pytest
from django.core.exceptions import ValidationError

from leaderlodge.games.models import GameParticipantResult
from leaderlodge.games.scoring import (
    apply_no_score_tie_scores,
    assign_results_from_scores,
    compute_double_weight,
    evaluate_results_from_rows,
    lineup_is_no_score_tie,
    no_score_tie_requested,
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


def test_unique_high_score_wins_dominos():
    rows = _rows([30, 20])
    evaluation = evaluate_results_from_rows(rows, "dominos")
    assert evaluation.win_pks == {0}
    assert evaluation.tie_pks == set()
    assert evaluation.loss_pks == set()
    assert evaluation.is_double is False


def test_low_score_wins_progressive_rummy():
    rows = _rows([50, 10, 20])
    evaluation = evaluate_results_from_rows(rows, "progressiverummy")
    assert evaluation.win_pks == {1}
    assert evaluation.loss_pks == {0}


def test_tied_high_scores_are_tie():
    rows = _rows([20, 20])
    evaluation = evaluate_results_from_rows(rows, "dominos")
    assert evaluation.win_pks == set()
    assert evaluation.tie_pks == {0, 1}


def test_tied_low_scores_are_both_wins():
    rows = _rows([30, 20, 20])
    evaluation = evaluate_results_from_rows(rows, "progressiverummy")
    assert evaluation.win_pks == set()
    assert evaluation.tie_pks == {1, 2}
    assert evaluation.loss_pks == {0}


def test_all_same_score_is_tie_without_loser():
    rows = _rows([25, 25, 25])
    evaluation = evaluate_results_from_rows(rows, "progressiverummy")
    assert evaluation.tie_pks == {0, 1, 2}
    assert evaluation.loss_pks == set()


def test_assign_placements_competition_ranking():
    rows = _rows([30, 20, 20])
    assign_results_from_scores(rows, "progressiverummy")
    assert rows[1]["placement"] == 1
    assert rows[2]["placement"] == 1
    assert rows[0]["placement"] == 2


def test_assign_placements_lower_place_tie_high_wins():
    rows = _rows([10, 8, 8])
    assign_results_from_scores(rows, "dominos")
    assert rows[0]["placement"] == 0
    assert rows[1]["placement"] == 2
    assert rows[2]["placement"] == 2


def test_assign_placements_mahjongg_wall_game():
    rows = _rows([35, 0, 0, 0])
    assign_results_from_scores(rows, "mahjongg")
    assert rows[0]["placement"] == 0
    assert rows[0]["result"] == Result.WIN
    assert rows[1]["placement"] == 3
    assert rows[2]["placement"] == 3
    assert rows[3]["placement"] == 3


def test_lineup_is_no_score_tie_for_mahjongg_tens():
    assert lineup_is_no_score_tie(_rows([10, 10, 10]), "mahjongg") is True
    assert lineup_is_no_score_tie(_rows([10, 10, 0]), "mahjongg") is False
    assert lineup_is_no_score_tie(_rows([10, 10]), "dominos") is False
    assert lineup_is_no_score_tie([], "mahjongg") is False


def test_apply_no_score_tie_scores_fills_mahjongg_tens():
    rows = _rows([10, 0, ""])
    apply_no_score_tie_scores(rows, "mahjongg")
    assert [row["score"] for row in rows] == [10, 10, 10]
    apply_no_score_tie_scores(rows, "dominos")
    assert [row["score"] for row in rows] == [10, 10, 10]


def test_no_score_tie_requested_reads_posted_checkbox():
    assert no_score_tie_requested({"is_no_score_tie": "1"}) is True
    assert no_score_tie_requested({"is_no_score_tie": "on"}) is True
    assert no_score_tie_requested({}) is False


@pytest.mark.parametrize(
    "scores,expected",
    [
        ({0: 42, 1: 19}, 1),
        ({0: 77, 1: 76}, 2),
        ({0: 39, 1: 61}, 2),
    ],
)
def test_compute_double_weight_dominos(scores, expected):
    rows = [
        {
            "player": FakePlayer(pk),
            "score": score,
            "result": Result.PLAYED,
        }
        for pk, score in scores.items()
    ]
    assign_results_from_scores(rows, "dominos")
    assert compute_double_weight(rows, "dominos") == expected


def test_assign_rejects_no_top_result():
    rows = []
    with pytest.raises(ValidationError):
        assign_results_from_scores(rows, "dominos")
