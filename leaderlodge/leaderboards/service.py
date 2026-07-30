"""
Leaderboard ranking for a group.

Rankings are scoped by game type. A player who plays both dominos and backgammon
receives one PlayerRanking row per game type (e.g. david-dominos, david-backgammon).

Rank score averages field-weighted finish points across weighted games played.
Each finish earns credit by placement; wins/ties/losses remain available as stats.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, replace
from datetime import date
from typing import TYPE_CHECKING

from django.db.models import Case, F, FloatField, Q, Sum, Value, When
from django.db.models.functions import Cast

from leaderlodge.games.list_stats import humanize_date_range
from leaderlodge.games.registry import GAME_TYPES, ScoreDirection, get_game_type
from leaderlodge.games.standings import standings_weight_expression
from leaderlodge.leaderboards.game_filters import apply_game_filters_to_results_qs
from leaderlodge.leaderboards.period import (
    LeaderboardPeriod,
    filter_results_by_period,
)
from leaderlodge.leaderboards.ranking import (
    FINISH_POINTS_EXPONENT,
    SORTABLE_COLUMNS,
    TIE_WIN_POINTS_FACTOR,
    FinishPointsCredit,
    compute_bayesian_factor,
    compute_display_rank_score,
    compute_finish_points,
    compute_half_game_penalty_factor,
    compute_percentage,
    compute_rank_score,
    rank_score_magnitude_for_result,
    ordinal_place_label,
    rank_score_sort_key,
    team_member_finish_credit,
)

if TYPE_CHECKING:
    from leaderlodge.games.models import Game
    from leaderlodge.groups.models import Group, GroupPlayer
    from leaderlodge.leaderboards.game_filters import LeaderboardGameFilters


@dataclass(frozen=True)
class PlayerRanking:
    """One player's standing for a single game type within a group."""

    player: GroupPlayer
    game_type_code: str
    game_type_name: str
    games_played: float
    wins: float
    losses: float
    win_points: float
    finish_points: float
    win_pct: float
    loss_pct: float
    rank_score: float
    rank: int | None = None


@dataclass(frozen=True)
class FieldSizeBreakdown:
    player_count: int
    weighted_count: float
    count_pct: float


@dataclass(frozen=True)
class PlacementBreakdown:
    placement: int
    label: str
    weighted_count: float
    finish_points: float
    avg_finish_points: float
    count_pct: float
    field_sizes: tuple[FieldSizeBreakdown, ...]


@dataclass(frozen=True)
class FieldSizeGameCount:
    player_count: int
    game_count: float
    count_pct: float


@dataclass(frozen=True)
class ScoreHighlight:
    score: int
    played_on: date


@dataclass(frozen=True)
class PlayerRankDetail:
    ranking: PlayerRanking
    raw_rank_score: float
    bayesian_factor: float
    bayesian_games_played: float
    bayesian_k: int
    rank_score_uses_simple_bayesian: bool
    half_game_penalty: float
    placements: tuple[PlacementBreakdown, ...]
    loss_game_count: float
    loss_pct: float
    loss_games_by_field_size: tuple[FieldSizeGameCount, ...]
    supports_loser: bool
    first_game_date: date | None
    last_game_date: date | None
    date_range_label: str
    first_win_date: date | None
    last_win_date: date | None
    first_loss_date: date | None
    game_count: int
    tie_count: int
    best_score: ScoreHighlight | None
    worst_score: ScoreHighlight | None
    score_low_wins: bool
    average_score: float | None
    average_field_size: float
    double_game_count: int
    half_game_count: int
    podium_count: int
    podium_pct: float
    finish_points_exponent: float


def _update_score_highlight(
    *,
    score: int,
    played_on: date,
    low_wins: bool,
    best: ScoreHighlight | None,
    worst: ScoreHighlight | None,
) -> tuple[ScoreHighlight, ScoreHighlight]:
    highlight = ScoreHighlight(score=score, played_on=played_on)
    if best is None:
        return highlight, highlight

    if low_wins:
        if score < best.score or (score == best.score and played_on < best.played_on):
            best = highlight
        if score > worst.score or (
            score == worst.score and played_on > worst.played_on
        ):
            worst = highlight
    else:
        if score > best.score or (score == best.score and played_on < best.played_on):
            best = highlight
        if score < worst.score or (
            score == worst.score and played_on > worst.played_on
        ):
            worst = highlight
    return best, worst


def _apply_location_filters(
    results_qs,
    *,
    location_id: int | None = None,
    location_ids: list[int] | None = None,
):
    if location_id is not None and location_ids is not None:
        raise ValueError("Provide location_id or location_ids, not both.")
    if location_id is not None:
        return results_qs.filter(game__location_id=location_id)
    if location_ids is not None:
        return results_qs.filter(game__location_id__in=location_ids)
    return results_qs


def get_player_rank_detail(
    group: Group,
    player: GroupPlayer,
    *,
    game_type_code: str,
    location_id: int | None = None,
    location_ids: list[int] | None = None,
    period: LeaderboardPeriod | None = None,
    game_size: int | None = None,
    game_filters: LeaderboardGameFilters | None = None,
) -> PlayerRankDetail | None:
    from django.conf import settings

    from leaderlodge.games.models import GameParticipantResult

    game_type = get_game_type(game_type_code)
    low_wins = game_type.score_direction == ScoreDirection.LOW_WINS
    if period is None:
        period = LeaderboardPeriod.all_time()
    from leaderlodge.groups.teams import results_queryset_for_player_credit

    results_qs = (
        results_queryset_for_player_credit(player)
        .filter(
            game__group=group,
            game__game_type_code=game_type_code,
        )
        .select_related("game")
        .prefetch_related("game__participant_results")
        .order_by("game__played_on", "game__pk", "pk")
    )
    results_qs = _apply_location_filters(
        results_qs, location_id=location_id, location_ids=location_ids
    )
    if game_size is not None:
        results_qs = results_qs.filter(game__player_count=game_size)
    if game_filters is not None:
        results_qs = apply_game_filters_to_results_qs(
            results_qs,
            game_filters,
            game_type_code=game_type_code,
        )
    results_qs = filter_results_by_period(results_qs, period)

    if not results_qs.exists():
        return None

    standings = _standings_for_game_type(
        group,
        game_type_code,
        location_id=location_id,
        location_ids=location_ids,
        period=period,
        game_size=game_size,
        game_filters=game_filters,
    )
    ranking_row = next((row for row in standings if row.player.pk == player.pk), None)
    if ranking_row is None:
        return None

    rankings = _assign_ranks(
        [row for row in standings if row.games_played > 0],
        low_wins=low_wins,
    )
    rank_by_player = {row.player.pk: row.rank for row in rankings}
    ranking = replace(ranking_row, rank=rank_by_player.get(player.pk))

    apply_team_finish_weight = period.apply_bayesian and not player.is_team

    placement_stats: dict[int, dict[str, object]] = defaultdict(
        lambda: {
            "weighted_count": 0.0,
            "finish_points": 0.0,
            "by_size": defaultdict(float),
        }
    )
    loss_games_by_size: dict[int, float] = defaultdict(float)
    loss_game_count = 0.0
    first_game_date: date | None = None
    last_game_date: date | None = None
    first_win_date: date | None = None
    last_win_date: date | None = None
    first_loss_date: date | None = None
    game_count = 0
    tie_count = 0
    double_game_count = 0
    half_game_count = 0
    podium_count = 0
    weighted_games = 0.0
    half_weighted_games = 0.0
    weighted_field_size = 0.0
    weighted_score_total = 0.0
    best_score: ScoreHighlight | None = None
    worst_score: ScoreHighlight | None = None

    for result in results_qs:
        game = result.game
        played_on = game.played_on
        weight = game.double_weight / game.half_weight
        if game.half_weight == 2:
            half_weighted_games += weight
        player_count = game.player_count
        placement = result.placement if result.placement is not None else 0
        game_count += 1

        if first_game_date is None or played_on < first_game_date:
            first_game_date = played_on
        if last_game_date is None or played_on > last_game_date:
            last_game_date = played_on

        if result.result == GameParticipantResult.Result.WIN:
            if first_win_date is None or played_on < first_win_date:
                first_win_date = played_on
            if last_win_date is None or played_on > last_win_date:
                last_win_date = played_on
        elif result.result == GameParticipantResult.Result.TIE:
            tie_count += 1

        if (
            game_type.supports_loser
            and result.result == GameParticipantResult.Result.LOSS
        ):
            loss_game_count += weight
            loss_games_by_size[player_count] += weight
            if first_loss_date is None or played_on < first_loss_date:
                first_loss_date = played_on

        if game.double_weight == 2:
            double_game_count += 1
        if game.half_weight == 2:
            half_game_count += 1

        if placement <= 2:
            podium_count += 1

        weighted_games += weight
        weighted_field_size += player_count * weight
        weighted_score_total += result.score * weight
        best_score, worst_score = _update_score_highlight(
            score=result.score,
            played_on=played_on,
            low_wins=low_wins,
            best=best_score,
            worst=worst_score,
        )

        bucket = placement_stats[placement]
        bucket["weighted_count"] = float(bucket["weighted_count"]) + weight
        finish_points = compute_finish_points(
            player_count=player_count,
            placement=placement,
            weight=weight,
            is_tie=result.result == GameParticipantResult.Result.TIE,
            score_magnitude=rank_score_magnitude_for_result(
                result.score,
                [
                    participant.score
                    for participant in result.game.participant_results.all()
                ],
                game_type_code=game_type_code,
                placement=placement,
            ),
        )
        if apply_team_finish_weight and result.player.is_team:
            finish_points = team_member_finish_credit(
                finish_points,
                member_games_played=ranking.games_played,
                apply_experience_weight=True,
            )
        bucket["finish_points"] = float(bucket["finish_points"]) + finish_points
        by_size = bucket["by_size"]
        by_size[player_count] = by_size[player_count] + weight

    average_field_size = (
        weighted_field_size / weighted_games if weighted_games > 0 else 0.0
    )
    average_score = (
        weighted_score_total / weighted_games if weighted_games > 0 else None
    )
    date_range_label = (
        humanize_date_range(first_game_date, last_game_date)
        if first_game_date and last_game_date
        else ""
    )

    raw_rank_score = compute_rank_score(
        points_total=ranking.finish_points,
        games_played=ranking.games_played,
    )
    from leaderlodge.groups.teams import effective_games_played_for_player

    games_played_by_id = {row.player.pk: row.games_played for row in standings}
    bayesian_games_played = effective_games_played_for_player(
        player, games_played_by_id
    )
    if period.apply_bayesian and raw_rank_score > 0:
        simple_factor = compute_bayesian_factor(bayesian_games_played)
        simple_rank_score = raw_rank_score * simple_factor
        rank_score_uses_simple_bayesian = (
            player.is_team or abs(simple_rank_score - ranking.rank_score) < 0.001
        )
        bayesian_factor = (
            simple_factor
            if rank_score_uses_simple_bayesian
            else ranking.rank_score / raw_rank_score
        )
    else:
        rank_score_uses_simple_bayesian = True
        bayesian_factor = 1.0
    half_game_penalty = compute_half_game_penalty_factor(
        weighted_games=weighted_games,
        half_weighted_games=half_weighted_games,
    )

    placement_denominator = weighted_games if weighted_games > 0 else 0.0

    placements: list[PlacementBreakdown] = []
    for placement in sorted(placement_stats):
        bucket = placement_stats[placement]
        weighted_count = float(bucket["weighted_count"])
        field_sizes = tuple(
            FieldSizeBreakdown(
                player_count=size,
                weighted_count=count,
                count_pct=compute_percentage(count, placement_denominator),
            )
            for size, count in sorted(bucket["by_size"].items())
        )
        placements.append(
            PlacementBreakdown(
                placement=placement,
                label=ordinal_place_label(placement),
                weighted_count=weighted_count,
                finish_points=float(bucket["finish_points"]),
                avg_finish_points=compute_rank_score(
                    points_total=float(bucket["finish_points"]),
                    games_played=weighted_count,
                ),
                count_pct=compute_percentage(weighted_count, placement_denominator),
                field_sizes=field_sizes,
            )
        )

    loss_games_by_field_size = tuple(
        FieldSizeGameCount(
            player_count=size,
            game_count=count,
            count_pct=compute_percentage(count, placement_denominator),
        )
        for size, count in sorted(loss_games_by_size.items())
    )
    loss_pct = compute_percentage(loss_game_count, placement_denominator)

    return PlayerRankDetail(
        ranking=ranking,
        raw_rank_score=raw_rank_score,
        bayesian_factor=bayesian_factor,
        bayesian_games_played=bayesian_games_played,
        bayesian_k=settings.LEADERBOARD_BAYESIAN_K,
        rank_score_uses_simple_bayesian=rank_score_uses_simple_bayesian,
        half_game_penalty=half_game_penalty,
        placements=tuple(placements),
        loss_game_count=loss_game_count,
        loss_pct=loss_pct,
        loss_games_by_field_size=loss_games_by_field_size,
        supports_loser=game_type.supports_loser,
        first_game_date=first_game_date,
        last_game_date=last_game_date,
        date_range_label=date_range_label,
        first_win_date=first_win_date,
        last_win_date=last_win_date,
        first_loss_date=first_loss_date,
        game_count=game_count,
        tie_count=tie_count,
        best_score=best_score,
        worst_score=worst_score,
        score_low_wins=low_wins,
        average_score=average_score,
        average_field_size=average_field_size,
        double_game_count=double_game_count,
        half_game_count=half_game_count,
        podium_count=podium_count,
        podium_pct=compute_percentage(podium_count, game_count),
        finish_points_exponent=FINISH_POINTS_EXPONENT,
    )


def get_player_rankings(
    group: Group,
    *,
    game_type_code: str | None = None,
    location_id: int | None = None,
    location_ids: list[int] | None = None,
    period: LeaderboardPeriod | None = None,
    game_size: int | None = None,
    player_type: str = "",
    game_filters: LeaderboardGameFilters | None = None,
) -> list[PlayerRanking]:
    """
    Return ranked players for a group, ordered by rank score.

    When game_type_code is set, only that game type is included.
    When game_type_code is None, all game types with recorded games are
    included. The same player may appear multiple times (once per game type).

    Players with no recorded games are omitted. Team sides credit the team
    entity at full value and each member at an experience-weighted share; solo
    results credit full finish points. See docs/rank-scoring.md.
    """
    if game_type_code is not None:
        game_type_codes = [game_type_code]
    else:
        game_type_codes = _game_type_codes_for_group(group)

    if period is None:
        period = LeaderboardPeriod.all_time()

    rankings: list[PlayerRanking] = []
    for code in game_type_codes:
        standings = _standings_for_game_type(
            group,
            code,
            location_id=location_id,
            location_ids=location_ids,
            period=period,
            game_size=game_size,
            player_type=player_type,
            game_filters=game_filters,
        )
        active = [row for row in standings if row.games_played > 0]
        low_wins = get_game_type(code).score_direction == ScoreDirection.LOW_WINS
        rankings.extend(_assign_ranks(active, low_wins=low_wins))

    return rankings


def get_group_roster_standings(
    group: Group,
    *,
    game_type_code: str,
    sort: str = "rank",
    ascending: bool = True,
    period: LeaderboardPeriod | None = None,
    game_size: int | None = None,
) -> list[PlayerRanking]:
    """
    Standings for every active roster player in a group for one game type.

    Players with no recorded games keep rank=None.
    """
    from leaderlodge.groups.models import GroupPlayer

    if period is None:
        period = LeaderboardPeriod.all_time()

    stats_by_player = {
        row.player.pk: row
        for row in _standings_for_game_type(
            group,
            game_type_code,
            period=period,
            game_size=game_size,
        )
    }
    game_type = get_game_type(game_type_code)

    rows: list[PlayerRanking] = []
    for player in group.players.filter(is_active=True).select_related("linked_user"):
        row = stats_by_player.get(player.pk)
        if row is None:
            row = _empty_player_ranking(player, game_type)
        rows.append(row)

    eligible = [row for row in rows if row.games_played > 0]
    low_wins = game_type.score_direction == ScoreDirection.LOW_WINS
    ranked = _assign_ranks(eligible, low_wins=low_wins)
    rank_by_player = {row.player.pk: row.rank for row in ranked}

    merged = [replace(row, rank=rank_by_player.get(row.player.pk)) for row in rows]
    return sort_standings(merged, sort=sort, ascending=ascending)


def sort_standings(
    rows: list[PlayerRanking],
    *,
    sort: str,
    ascending: bool,
) -> list[PlayerRanking]:
    if sort not in SORTABLE_COLUMNS:
        sort = "rank"

    def key(row: PlayerRanking):
        if sort == "rank":
            return row.rank if row.rank is not None else 10**9
        if sort == "name":
            return row.player.display_label.lower()
        if sort == "score":
            return row.rank_score
        if sort == "games":
            return row.games_played
        if sort == "wins":
            return row.wins
        if sort == "win_pct":
            return row.win_pct
        if sort == "losses":
            return row.losses
        return row.loss_pct

    return sorted(rows, key=key, reverse=not ascending)


def get_player_stats(
    group: Group,
    player: GroupPlayer,
) -> dict[str, dict[str, int | float]]:
    """
    Basic stats keyed by game_type_code: games_played, wins, win_pct.
    """
    from leaderlodge.games.models import GameParticipantResult

    weight = standings_weight_expression()
    rows = (
        GameParticipantResult.objects.filter(game__group=group, player=player)
        .values("game__game_type_code")
        .annotate(
            games_played=Sum(weight),
            wins=Sum(
                weight,
                filter=Q(result=GameParticipantResult.Result.WIN),
            ),
        )
    )

    stats: dict[str, dict[str, int | float]] = defaultdict(
        lambda: {"games_played": 0, "wins": 0, "win_pct": 0.0}
    )
    for row in rows:
        code = row["game__game_type_code"]
        games_played = row["games_played"] or 0
        wins = row["wins"] or 0
        stats[code] = {
            "games_played": games_played,
            "wins": wins,
            "win_pct": compute_percentage(wins, games_played),
        }

    for code in stats:
        game_type = GAME_TYPES.get(code)
        if game_type:
            stats[code]["game_type_name"] = game_type.name

    return dict(stats)


def _game_type_codes_for_group(group: Group) -> list[str]:
    from leaderlodge.games.models import Game

    codes = (
        Game.objects.filter(group=group)
        .values_list("game_type_code", flat=True)
        .distinct()
        .order_by("game_type_code")
    )
    return list(codes)


def _standings_weight_factors():
    weight = standings_weight_expression()
    player_count = Cast(F("game__player_count"), FloatField())
    return weight, player_count


def _finish_points_by_player(
    results_qs,
    *,
    game_type_code: str,
    games_played_by_id: dict[int, float] | None = None,
    apply_experience_weight: bool = False,
) -> dict[int, FinishPointsCredit]:
    from leaderlodge.games.models import GameParticipantResult
    from leaderlodge.groups.teams import team_member_players

    results = list(
        results_qs.select_related("player", "game").prefetch_related(
            "player__team_members__member"
        )
    )
    if not results:
        return {}

    game_scores: dict[int, list[float]] = defaultdict(list)
    for result in results:
        game_scores[result.game_id].append(result.score)

    totals: dict[int, FinishPointsCredit] = defaultdict(FinishPointsCredit)
    for result in results:
        weight = result.game.double_weight / result.game.half_weight
        points = compute_finish_points(
            player_count=result.game.player_count,
            placement=result.placement if result.placement is not None else 0,
            weight=weight,
            is_tie=result.result == GameParticipantResult.Result.TIE,
            score_magnitude=rank_score_magnitude_for_result(
                result.score,
                game_scores[result.game_id],
                game_type_code=game_type_code,
                placement=result.placement if result.placement is not None else 0,
            ),
        )
        if result.player.is_team:
            team_credit = totals[result.player.pk]
            team_credit.solo += points
            for member in team_member_players(result.player):
                member_games = (
                    float(games_played_by_id.get(member.pk, 0.0))
                    if games_played_by_id is not None
                    else 0.0
                )
                member_credit = totals[member.pk]
                member_credit.team += team_member_finish_credit(
                    points,
                    member_games_played=member_games,
                    apply_experience_weight=apply_experience_weight,
                )
            continue

        solo_credit = totals[result.player.pk]
        solo_credit.solo += points

    return dict(totals)


def filter_results_through_game(
    results_qs,
    game: Game,
    *,
    include_game: bool,
):
    """Limit participant results to games at or before a cutoff game."""
    if include_game:
        return results_qs.filter(
            Q(game__played_on__lt=game.played_on)
            | Q(game__played_on=game.played_on, game__pk__lte=game.pk)
        )
    return results_qs.filter(
        Q(game__played_on__lt=game.played_on)
        | Q(game__played_on=game.played_on, game__pk__lt=game.pk)
    )


def get_standings_at_game(
    group: Group,
    game_type_code: str,
    game: Game,
    *,
    include_game: bool,
) -> list[PlayerRanking]:
    """Leaderboard standings using only games through the cutoff game."""
    from leaderlodge.games.models import GameParticipantResult

    period = LeaderboardPeriod.all_time()
    results_qs = GameParticipantResult.objects.filter(
        game__group=group,
        game__game_type_code=game_type_code,
    )
    results_qs = filter_results_by_period(results_qs, period)
    results_qs = filter_results_through_game(
        results_qs, game, include_game=include_game
    )
    return _standings_for_game_type(
        group,
        game_type_code,
        period=period,
        results_qs=results_qs,
    )


def get_ranked_standings_at_game(
    group: Group,
    game_type_code: str,
    game: Game,
    *,
    include_game: bool,
) -> list[PlayerRanking]:
    standings = get_standings_at_game(
        group,
        game_type_code,
        game,
        include_game=include_game,
    )
    active = [row for row in standings if row.games_played > 0]
    low_wins = get_game_type(game_type_code).score_direction == ScoreDirection.LOW_WINS
    return _assign_ranks(active, low_wins=low_wins)


def _standings_for_game_type(
    group: Group,
    game_type_code: str,
    *,
    location_id: int | None = None,
    location_ids: list[int] | None = None,
    period: LeaderboardPeriod | None = None,
    game_size: int | None = None,
    results_qs=None,
    player_type: str = "",
    game_filters: LeaderboardGameFilters | None = None,
) -> list[PlayerRanking]:
    from leaderlodge.games.models import GameParticipantResult
    from leaderlodge.groups.teams import (
        effective_games_played_for_player,
        leaderboard_credit_players,
        matches_player_type,
    )

    game_type = get_game_type(game_type_code)
    low_wins = game_type.score_direction == ScoreDirection.LOW_WINS

    if period is None:
        period = LeaderboardPeriod.all_time()

    if results_qs is None:
        results_qs = GameParticipantResult.objects.filter(
            game__group=group,
            game__game_type_code=game_type_code,
        )
        results_qs = _apply_location_filters(
            results_qs, location_id=location_id, location_ids=location_ids
        )
        if game_size is not None:
            results_qs = results_qs.filter(game__player_count=game_size)
        if game_filters is not None:
            results_qs = apply_game_filters_to_results_qs(
                results_qs,
                game_filters,
                game_type_code=game_type_code,
            )
        results_qs = filter_results_by_period(results_qs, period)

    results = list(
        results_qs.select_related(
            "player", "player__linked_user", "game"
        ).prefetch_related(
            "player__team_members__member",
            "player__team_members__member__linked_user",
        )
    )

    stats: dict[int, dict[str, float]] = defaultdict(
        lambda: {
            "games_played": 0.0,
            "half_weighted_games": 0.0,
            "wins": 0.0,
            "losses": 0.0,
            "win_points": 0.0,
        }
    )
    players_by_id: dict[int, GroupPlayer] = {}

    for result in results:
        weight = result.game.double_weight / result.game.half_weight
        field_size = float(result.game.player_count)
        for credited in leaderboard_credit_players(result.player):
            players_by_id[credited.pk] = credited
            row = stats[credited.pk]
            row["games_played"] += weight
            if result.game.half_weight == 2:
                row["half_weighted_games"] += weight
            if result.result == GameParticipantResult.Result.WIN:
                row["wins"] += weight
                row["win_points"] += field_size * weight
            elif result.result == GameParticipantResult.Result.LOSS:
                row["losses"] += weight
            elif result.result == GameParticipantResult.Result.TIE:
                row["win_points"] += field_size * weight * TIE_WIN_POINTS_FACTOR

    games_played_by_id = {
        player_id: row["games_played"] for player_id, row in stats.items()
    }
    finish_points_by_player = _finish_points_by_player(
        results_qs,
        game_type_code=game_type_code,
        games_played_by_id=games_played_by_id,
        apply_experience_weight=period.apply_bayesian,
    )

    rows: list[PlayerRanking] = []
    for player_id, row in stats.items():
        player = players_by_id[player_id]
        if not matches_player_type(player, player_type):
            continue
        games_played = row["games_played"]
        effective_games = effective_games_played_for_player(player, games_played_by_id)
        wins = row["wins"]
        losses = row["losses"]
        win_points = row["win_points"]
        credit = finish_points_by_player.get(player.pk, FinishPointsCredit())
        finish_points = credit.total
        raw_rank_score = compute_rank_score(
            points_total=finish_points,
            games_played=games_played,
        )
        half_game_penalty = compute_half_game_penalty_factor(
            weighted_games=games_played,
            half_weighted_games=row["half_weighted_games"],
        )
        rank_score = compute_display_rank_score(
            credit=credit,
            games_played=games_played,
            player_is_team=player.is_team,
            effective_games_for_bayesian=effective_games,
            apply_bayesian=period.apply_bayesian,
        )
        rows.append(
            PlayerRanking(
                player=player,
                game_type_code=game_type.code,
                game_type_name=game_type.name,
                games_played=games_played,
                wins=wins,
                losses=losses,
                win_points=win_points,
                finish_points=finish_points,
                win_pct=compute_percentage(wins, games_played),
                loss_pct=compute_percentage(losses, games_played),
                rank_score=rank_score,
            )
        )

    return rows


def _empty_player_ranking(player: GroupPlayer, game_type) -> PlayerRanking:
    return PlayerRanking(
        player=player,
        game_type_code=game_type.code,
        game_type_name=game_type.name,
        games_played=0.0,
        wins=0.0,
        losses=0.0,
        win_points=0.0,
        finish_points=0.0,
        win_pct=0.0,
        loss_pct=0.0,
        rank_score=0.0,
    )


def _assign_ranks(
    rows: list[PlayerRanking],
    *,
    low_wins: bool = False,
) -> list[PlayerRanking]:
    ordered = sorted(
        rows,
        key=lambda row: rank_score_sort_key(row, low_wins=low_wins),
    )
    ranked: list[PlayerRanking] = []
    current_rank = 1
    for i, row in enumerate(ordered):
        if i > 0:
            prev = ordered[i - 1]
            # Advance rank only when the rank-determining fields differ.
            # display_label is a tiebreaker for stable ordering only.
            prev_key = rank_score_sort_key(prev, low_wins=low_wins)[:3]
            curr_key = rank_score_sort_key(row, low_wins=low_wins)[:3]
            if curr_key != prev_key:
                current_rank = i + 1
        ranked.append(replace(row, rank=current_rank))
    return ranked
