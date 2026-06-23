import pytest
from django.core.exceptions import ValidationError

from leaderlodge.games.models import GameParticipantResult
from leaderlodge.games.scoring import (
    assign_results_from_scores,
    compute_double_weight,
    evaluate_results_from_rows,
    player_count_is_valid,
    record_game_rules_summary,
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


def test_assign_results_from_scores():
    rows = _rows([10, 20])
    assign_results_from_scores(rows, "dominos")
    assert rows[1]["result"] == Result.WIN
    assert rows[0]["result"] == Result.PLAYED
    assert rows[1]["placement"] == 0
    assert rows[0]["placement"] == 1


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


def test_player_count_is_valid():
    assert player_count_is_valid(2, "dominos") is True
    assert player_count_is_valid(3, "dominos") is True
    assert player_count_is_valid(1, "dominos") is False
    assert player_count_is_valid(4, "dominos") is False


def test_record_game_rules_summary():
    assert record_game_rules_summary("dominos") == "Highest score wins, 2–3 players."
    assert record_game_rules_summary("backgammon") == "Highest score wins, 2 players."
    assert (
        record_game_rules_summary("progressiverummy")
        == "Lowest score wins, 2–10 players."
    )


def test_assign_rejects_no_top_result():
    rows = []
    with pytest.raises(ValidationError):
        assign_results_from_scores(rows, "dominos")
