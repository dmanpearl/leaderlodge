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


def compute_finish_points(
    *,
    player_count: float,
    placement: float,
    weight: float = 1.0,
    is_tie: bool = False,
) -> float:
    """
    Field-weighted finish credit for one game result.

    First place earns player_count × weight; last place earns 0. Intermediate
    placements scale linearly. Ties keep the historical half-credit factor.
    """
    if player_count <= 1:
        return 0.0

    slots_above_last = player_count - 1.0
    placement_distance = max(player_count - placement - 1.0, 0.0)
    points = placement_distance / slots_above_last * player_count * weight
    if is_tie:
        points *= TIE_WIN_POINTS_FACTOR
    return points


def compute_rank_score(*, points_total: float, games_played: float) -> float:
    if games_played <= 0:
        return 0.0
    return points_total / games_played


def compute_vesting_multiplier(
    games_played: float,
    *,
    vesting_count: int | None = None,
    vesting_factor: float | None = None,
) -> float:
    if games_played <= 0:
        return 0.0

    from django.conf import settings

    if vesting_count is None:
        vesting_count = settings.LEADERBOARD_VESTING_COUNT
    if vesting_factor is None:
        vesting_factor = settings.LEADERBOARD_VESTING_FACTOR

    if games_played >= vesting_count:
        return 1.0

    progress = games_played / vesting_count
    return vesting_factor + (1.0 - vesting_factor) * progress


def compute_linear_vesting_multiplier(
    games_played: float,
    *,
    vesting_count: int,
    vesting_factor: float,
) -> float:
    """Original linear ramp for comparison charts and documentation."""
    if games_played <= 0:
        return 0.0
    if games_played >= vesting_count:
        return 1.0
    return vesting_factor * games_played / vesting_count


def apply_vesting_to_rank_score(
    raw_rank_score: float,
    games_played: float,
) -> float:
    return raw_rank_score * compute_vesting_multiplier(games_played)


def compute_percentage(numerator: float, denominator: float) -> float:
    if denominator <= 0:
        return 0.0
    return numerator / denominator * 100
