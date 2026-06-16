"""Score-based result assignment (shared rules for server and client)."""

from dataclasses import dataclass, field

from django.core.exceptions import ValidationError

from leaderlodge.games.models import GameParticipantResult
from leaderlodge.games.registry import get_game_type

Result = GameParticipantResult.Result


@dataclass
class ScoreEvaluation:
    win_pks: set[int] = field(default_factory=set)
    tie_pks: set[int] = field(default_factory=set)
    loss_pks: set[int] = field(default_factory=set)
    error: str | None = None
    player_count: int = 0


def evaluate_results_from_rows(
    rows: list[dict], game_type_code: str
) -> ScoreEvaluation:
    game_type = get_game_type(game_type_code)
    count = len(rows)
    if count == 0:
        return ScoreEvaluation(player_count=0)

    max_score = max(row["score"] for row in rows)
    min_score = min(row["score"] for row in rows)
    at_max = [row for row in rows if row["score"] == max_score]
    at_min = [row for row in rows if row["score"] == min_score]

    win_pks: set[int] = set()
    tie_pks: set[int] = set()
    loss_pks: set[int] = set()

    if len(at_max) == 1:
        win_pks.add(at_max[0]["player"].pk)
    else:
        for row in at_max:
            tie_pks.add(row["player"].pk)

    if game_type.supports_loser and max_score != min_score:
        for row in at_min:
            loss_pks.add(row["player"].pk)

    return ScoreEvaluation(
        win_pks=win_pks,
        tie_pks=tie_pks,
        loss_pks=loss_pks,
        player_count=count,
    )


def assign_results_from_scores(rows: list[dict], game_type_code: str) -> None:
    evaluation = evaluate_results_from_rows(rows, game_type_code)

    for row in rows:
        pk = row["player"].pk
        if pk in evaluation.win_pks:
            row["result"] = Result.WIN
        elif pk in evaluation.tie_pks:
            row["result"] = Result.TIE
        elif pk in evaluation.loss_pks:
            row["result"] = Result.LOSS
        else:
            row["result"] = Result.PLAYED

    game_type = get_game_type(game_type_code)
    game_type.validate(
        player_count=len(rows),
        winner_count=sum(1 for row in rows if row["result"] == Result.WIN),
        tie_count=sum(1 for row in rows if row["result"] == Result.TIE),
        loser_count=sum(1 for row in rows if row["result"] == Result.LOSS),
    )


def player_count_is_valid(count: int, game_type_code: str) -> bool:
    game_type = get_game_type(game_type_code)
    return game_type.min_players <= count <= game_type.max_players


# Backward-compatible alias for tests importing the old name.
assign_winner_loser_from_scores = assign_results_from_scores
