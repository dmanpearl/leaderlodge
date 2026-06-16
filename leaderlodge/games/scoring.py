"""Score-based result assignment (shared rules for server and client)."""

from dataclasses import dataclass, field

from django.core.exceptions import ValidationError

from leaderlodge.games.models import GameParticipantResult
from leaderlodge.games.registry import ScoreDirection, get_game_type

Result = GameParticipantResult.Result


@dataclass
class ScoreEvaluation:
    win_pks: set[int] = field(default_factory=set)
    tie_pks: set[int] = field(default_factory=set)
    loss_pks: set[int] = field(default_factory=set)
    error: str | None = None
    player_count: int = 0
    is_double: bool = False


def evaluate_results_from_rows(
    rows: list[dict], game_type_code: str
) -> ScoreEvaluation:
    game_type = get_game_type(game_type_code)
    count = len(rows)
    if count == 0:
        return ScoreEvaluation(player_count=0)

    scores = [row["score"] for row in rows]
    best_score = (
        min(scores)
        if game_type.score_direction == ScoreDirection.LOW_WINS
        else max(scores)
    )
    worst_score = (
        max(scores)
        if game_type.score_direction == ScoreDirection.LOW_WINS
        else min(scores)
    )
    at_best = [row for row in rows if row["score"] == best_score]
    at_worst = [row for row in rows if row["score"] == worst_score]

    win_pks: set[int] = set()
    tie_pks: set[int] = set()
    loss_pks: set[int] = set()

    if len(at_best) == 1:
        win_pks.add(at_best[0]["player"].pk)
    else:
        for row in at_best:
            tie_pks.add(row["player"].pk)

    if game_type.supports_loser and best_score != worst_score:
        for row in at_worst:
            loss_pks.add(row["player"].pk)

    is_double = False
    if game_type.win_target_score and len(win_pks) == 1:
        winner_score = next(row["score"] for row in rows if row["player"].pk in win_pks)
        is_double = winner_score >= 2 * game_type.win_target_score

    return ScoreEvaluation(
        win_pks=win_pks,
        tie_pks=tie_pks,
        loss_pks=loss_pks,
        player_count=count,
        is_double=is_double,
    )


def assign_placements(rows: list[dict], game_type_code: str) -> None:
    game_type = get_game_type(game_type_code)
    reverse = game_type.score_direction == ScoreDirection.HIGH_WINS
    sorted_rows = sorted(rows, key=lambda row: row["score"], reverse=reverse)

    placement = 0
    index = 0
    while index < len(sorted_rows):
        score = sorted_rows[index]["score"]
        tied = [row for row in sorted_rows if row["score"] == score]
        for row in tied:
            row["placement"] = placement
        index += len(tied)
        placement += len(tied)


def compute_double_weight(rows: list[dict], game_type_code: str) -> int:
    evaluation = evaluate_results_from_rows(rows, game_type_code)
    return 2 if evaluation.is_double else 1


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

    assign_placements(rows, game_type_code)

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


assign_winner_loser_from_scores = assign_results_from_scores
