"""Rank algorithm codes, labels, and sort keys for the leaderboard selector."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from leaderlodge.leaderboards.ranking import rank_score_sort_key

ALGORITHM_BAYESIAN = "bayesian"
ALGORITHM_WIN_PERCENT = "win_percent"
ALGORITHM_WIN_TOTAL = "win_total"

DEFAULT_ALGORITHM = ALGORITHM_BAYESIAN

RANK_ALGORITHM_CHOICES: tuple[tuple[str, str], ...] = (
    (ALGORITHM_BAYESIAN, "Bayesian (default)"),
    (ALGORITHM_WIN_PERCENT, "Win Percent"),
    (ALGORITHM_WIN_TOTAL, "Wins Total"),
)

_VALID_ALGORITHMS = frozenset(code for code, _ in RANK_ALGORITHM_CHOICES)

_LABELS = dict(RANK_ALGORITHM_CHOICES)

# Primary column header when the Score column shows the ranking metric.
SCORE_COLUMN_HEADERS: dict[str, str] = {
    ALGORITHM_BAYESIAN: "Score",
    ALGORITHM_WIN_PERCENT: "Win %",
    ALGORITHM_WIN_TOTAL: "Wins",
}


def resolve_rank_algorithm(raw: str | None) -> str:
    """Return a valid algorithm code; invalid or empty becomes Bayesian."""
    cleaned = (raw or "").strip().lower()
    if cleaned in _VALID_ALGORITHMS:
        return cleaned
    return DEFAULT_ALGORITHM


def rank_algorithm_label(algorithm: str) -> str:
    return _LABELS.get(resolve_rank_algorithm(algorithm), _LABELS[DEFAULT_ALGORITHM])


def rank_algorithm_summary_label(algorithm: str) -> str:
    """Short label for filter summary; empty when Bayesian (default)."""
    code = resolve_rank_algorithm(algorithm)
    if code == ALGORITHM_BAYESIAN:
        return ""
    if code == ALGORITHM_WIN_PERCENT:
        return "Win Percent"
    if code == ALGORITHM_WIN_TOTAL:
        return "Wins Total"
    return ""


def score_column_header(algorithm: str) -> str:
    return SCORE_COLUMN_HEADERS.get(
        resolve_rank_algorithm(algorithm),
        SCORE_COLUMN_HEADERS[DEFAULT_ALGORITHM],
    )


def win_percent_sort_key(row: Any, *, low_wins: bool = False) -> tuple:
    del low_wins
    return (
        -row.win_pct,
        -row.wins,
        -row.games_played,
        row.player.display_label.lower(),
    )


def win_total_sort_key(row: Any, *, low_wins: bool = False) -> tuple:
    del low_wins
    return (
        -row.wins,
        -row.win_pct,
        -row.games_played,
        row.player.display_label.lower(),
    )


def sort_key_for_algorithm(
    algorithm: str,
) -> Callable[..., tuple]:
    code = resolve_rank_algorithm(algorithm)
    if code == ALGORITHM_WIN_PERCENT:
        return win_percent_sort_key
    if code == ALGORITHM_WIN_TOTAL:
        return win_total_sort_key
    return rank_score_sort_key
