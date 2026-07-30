from __future__ import annotations

from dataclasses import dataclass

TIE_WIN_POINTS_FACTOR = 0.5
FINISH_POINTS_EXPONENT = 1.0
LOW_WINS_REFERENCE_SCORE = 500


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


def compute_score_magnitude(
    score: float,
    game_scores: list[float],
    *,
    low_wins: bool,
    placement: int,
) -> float:
    """
    Raw score credit for one finish, oriented so higher is better.

    High-wins games use the recorded score. Low-wins winners use a fixed
    reference minus their score (performance alone). Other low-wins finishers
    use field max minus score so a close second earns more than a far second.
    """
    score = float(score)
    if low_wins:
        if placement == 0:
            return max(LOW_WINS_REFERENCE_SCORE - score, 0.0)
        field_max = max(game_scores)
        return max(field_max - score, 0.0)
    return score


def rank_score_magnitude_for_result(
    score: float,
    game_scores: list[float],
    *,
    game_type_code: str,
    placement: int,
) -> float:
    """
    Score magnitude for rank credit on one finish.

    When the game type sets rank_uses_score_magnitude=False (pickleball), returns
    1.0 so wins and placement drive rank score without margin of victory.
    """
    from leaderlodge.games.registry import (
        ScoreDirection,
        game_type_rank_uses_score_magnitude,
        get_game_type,
    )

    if not game_type_rank_uses_score_magnitude(game_type_code):
        return 1.0
    game_type = get_game_type(game_type_code)
    low_wins = game_type.score_direction == ScoreDirection.LOW_WINS
    return compute_score_magnitude(
        score,
        game_scores,
        low_wins=low_wins,
        placement=placement,
    )


def compute_finish_points(
    *,
    player_count: float,
    placement: float,
    weight: float = 1.0,
    is_tie: bool = False,
    score_magnitude: float | None = None,
) -> float:
    """
    Field-weighted finish credit for one game result.

    finish = placement_ratio x player_count x weight x score_magnitude
    Ties multiply by TIE_WIN_POINTS_FACTOR.
    """
    if player_count <= 1:
        return 0.0

    slots_above_last = player_count - 1.0
    placement_distance = max(player_count - placement - 1.0, 0.0)
    ratio = placement_distance / slots_above_last
    points = (ratio**FINISH_POINTS_EXPONENT) * player_count * weight
    if is_tie:
        points *= TIE_WIN_POINTS_FACTOR
    if score_magnitude is not None:
        points *= score_magnitude
    return points


def compute_rank_score(*, points_total: float, games_played: float) -> float:
    if games_played <= 0:
        return 0.0
    return points_total / games_played


def compute_bayesian_factor(
    games_played: float,
    *,
    k: int | None = None,
) -> float:
    if games_played <= 0:
        return 0.0

    from django.conf import settings

    if k is None:
        k = settings.LEADERBOARD_BAYESIAN_K

    return games_played / (games_played + k)


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


def apply_bayesian_to_rank_score(
    raw_rank_score: float,
    games_played: float,
    *,
    apply_bayesian: bool = True,
) -> float:
    if not apply_bayesian:
        return raw_rank_score

    factor = compute_bayesian_factor(games_played)
    if factor <= 0:
        return 0.0

    return raw_rank_score * factor


@dataclass
class FinishPointsCredit:
    """Finish points credited to one leaderboard row, split by source."""

    solo: float = 0.0
    team: float = 0.0

    @property
    def total(self) -> float:
        return self.solo + self.team


def team_member_finish_credit(
    side_finish_points: float,
    *,
    member_games_played: float,
    apply_experience_weight: bool,
) -> float:
    """
    Experience-weighted finish credit for an individual from a team side.

    When enabled, scales side finish points by the member's Bayesian factor
    so rookies receive less individual credit from team wins.
    """
    if not apply_experience_weight:
        return side_finish_points
    return side_finish_points * compute_bayesian_factor(member_games_played)


def compute_display_rank_score(
    *,
    credit: FinishPointsCredit,
    games_played: float,
    player_is_team: bool,
    effective_games_for_bayesian: float,
    apply_bayesian: bool,
) -> float:
    """
    Final rank score for display and sort order.

    Individuals: Bayesian applies to solo-sourced points only; team-sourced
    points are pre-weighted at credit time. Team entities: full side credit
    with Bayesian on collective member experience.
    """
    if games_played <= 0:
        return 0.0
    if not apply_bayesian:
        return credit.total / games_played
    if player_is_team:
        raw_rank_score = credit.total / games_played
        return apply_bayesian_to_rank_score(
            raw_rank_score,
            effective_games_for_bayesian,
        )
    solo_raw = credit.solo / games_played
    team_raw = credit.team / games_played
    return solo_raw * compute_bayesian_factor(games_played) + team_raw


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
