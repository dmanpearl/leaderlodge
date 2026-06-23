from __future__ import annotations

TIE_WIN_POINTS_FACTOR = 0.5
FINISH_POINTS_EXPONENT = 1.5

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


def ordinal_place_label(placement: int) -> str:
    place = placement + 1
    if 10 <= place % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(place % 10, "th")
    return f"{place}{suffix}"


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
    placements scale by (normalized distance)^FINISH_POINTS_EXPONENT.
    Ties multiply that amount by TIE_WIN_POINTS_FACTOR.
    """
    if player_count <= 1:
        return 0.0

    slots_above_last = player_count - 1.0
    placement_distance = max(player_count - placement - 1.0, 0.0)
    ratio = placement_distance / slots_above_last
    points = (ratio**FINISH_POINTS_EXPONENT) * player_count * weight
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


LOW_WINS_VESTING_EXPONENT = 2.0


def compute_half_game_penalty_factor(
    *,
    weighted_games: float,
    half_weighted_games: float,
) -> float:
    """
    Reserved for a future Progressive Rummy half-game rank adjustment.

    Half games still count at 0.5x in games/wins/finish totals; rank score does
    not apply an extra multiplier yet.
    """
    return 1.0


def apply_vesting_to_rank_score(
    raw_rank_score: float,
    games_played: float,
    *,
    low_wins: bool = False,
    half_game_penalty: float = 1.0,
) -> float:
    vesting_multiplier = compute_vesting_multiplier(games_played)
    if vesting_multiplier <= 0:
        return 0.0

    if low_wins:
        return raw_rank_score * (vesting_multiplier**LOW_WINS_VESTING_EXPONENT)

    return raw_rank_score * vesting_multiplier


def rank_score_sort_key(
    row,
    *,
    low_wins: bool = False,
) -> tuple:
    """Sort key for rank assignment: higher rank score is better."""
    del low_wins
    return (
        -row.rank_score,
        -row.games_played,
        -row.finish_points,
        row.player.display_label.lower(),
    )


def compute_percentage(numerator: float, denominator: float) -> float:
    if denominator <= 0:
        return 0.0
    return numerator / denominator * 100
