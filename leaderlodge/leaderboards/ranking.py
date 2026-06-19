from __future__ import annotations

TIE_WIN_POINTS_FACTOR = 0.5

SORTABLE_COLUMNS = frozenset(
    {
        "rank",
        "name",
        "score",
        "games",
        "wins",
        "win_pct",
        "losses",
        "loss_pct",
    }
)


def compute_rank_score(*, win_points: float, games_played: float) -> float:
    if games_played <= 0:
        return 0.0
    return win_points / games_played


def compute_percentage(numerator: float, denominator: float) -> float:
    if denominator <= 0:
        return 0.0
    return numerator / denominator * 100
