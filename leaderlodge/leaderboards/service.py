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
from typing import TYPE_CHECKING

from django.db.models import Case, F, FloatField, Q, Sum, Value, When
from django.db.models.functions import Cast, Greatest

from leaderlodge.games.registry import GAME_TYPES, get_game_type
from leaderlodge.games.standings import standings_weight_expression
from leaderlodge.leaderboards.ranking import (
    SORTABLE_COLUMNS,
    TIE_WIN_POINTS_FACTOR,
    apply_vesting_to_rank_score,
    compute_percentage,
    compute_rank_score,
)

if TYPE_CHECKING:
    from leaderlodge.groups.models import Group, GroupPlayer


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


def get_player_rankings(
    group: Group,
    *,
    game_type_code: str | None = None,
    location_id: int | None = None,
) -> list[PlayerRanking]:
    """
    Return ranked players for a group, ordered by vested rank score.

    When game_type_code is set, only that game type is included.
    When game_type_code is None, all game types with recorded games are
    included. The same player may appear multiple times (once per game type).

    Players with no recorded games are omitted. Low game counts reduce the
    displayed rank score via the vesting multiplier in settings.
    """
    if game_type_code is not None:
        game_type_codes = [game_type_code]
    else:
        game_type_codes = _game_type_codes_for_group(group)

    rankings: list[PlayerRanking] = []
    for code in game_type_codes:
        standings = _standings_for_game_type(
            group,
            code,
            location_id=location_id,
        )
        active = [row for row in standings if row.games_played > 0]
        rankings.extend(_assign_ranks(active))

    return rankings


def get_group_roster_standings(
    group: Group,
    *,
    game_type_code: str,
    sort: str = "rank",
    ascending: bool = True,
) -> list[PlayerRanking]:
    """
    Standings for every active roster player in a group for one game type.

    Players with no recorded games keep rank=None.
    """
    from leaderlodge.groups.models import GroupPlayer

    stats_by_player = {
        row.player.pk: row
        for row in _standings_for_game_type(group, game_type_code)
    }
    game_type = get_game_type(game_type_code)

    rows: list[PlayerRanking] = []
    for player in group.players.filter(is_active=True).select_related("linked_user"):
        row = stats_by_player.get(player.pk)
        if row is None:
            row = _empty_player_ranking(player, game_type)
        rows.append(row)

    eligible = [row for row in rows if row.games_played > 0]
    ranked = _assign_ranks(eligible)
    rank_by_player = {row.player.pk: row.rank for row in ranked}

    merged = [
        replace(row, rank=rank_by_player.get(row.player.pk))
        for row in rows
    ]
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


def _finish_points_expression():
    from leaderlodge.games.models import GameParticipantResult

    weight, player_count = _standings_weight_factors()
    placement = Cast(F("placement"), FloatField())
    slots_above_last = Greatest(player_count - Value(1.0), Value(1.0))
    placement_distance = Greatest(
        player_count - placement - Value(1.0),
        Value(0.0),
    )
    base = placement_distance / slots_above_last * player_count * weight
    return Case(
        When(
            result=GameParticipantResult.Result.TIE,
            then=base * Value(TIE_WIN_POINTS_FACTOR),
        ),
        default=base,
    )


def _standings_for_game_type(
    group: Group,
    game_type_code: str,
    *,
    location_id: int | None = None,
) -> list[PlayerRanking]:
    from leaderlodge.games.models import GameParticipantResult
    from leaderlodge.groups.models import GroupPlayer

    game_type = get_game_type(game_type_code)

    results_qs = GameParticipantResult.objects.filter(
        game__group=group,
        game__game_type_code=game_type_code,
    )
    if location_id is not None:
        results_qs = results_qs.filter(game__location_id=location_id)

    weight, player_count = _standings_weight_factors()
    win_points_expr = player_count * weight
    tie_points_expr = player_count * weight * Value(TIE_WIN_POINTS_FACTOR)

    finish_points_expr = _finish_points_expression()

    stats = results_qs.values("player_id").annotate(
        games_played=Sum(weight),
        wins=Sum(weight, filter=Q(result=GameParticipantResult.Result.WIN)),
        losses=Sum(weight, filter=Q(result=GameParticipantResult.Result.LOSS)),
        win_point_wins=Sum(
            win_points_expr,
            filter=Q(result=GameParticipantResult.Result.WIN),
        ),
        win_point_ties=Sum(
            tie_points_expr,
            filter=Q(result=GameParticipantResult.Result.TIE),
        ),
        finish_points=Sum(finish_points_expr),
    )

    players_by_id = {
        player.pk: player
        for player in GroupPlayer.objects.filter(
            pk__in=[row["player_id"] for row in stats]
        ).select_related("linked_user")
    }

    rows: list[PlayerRanking] = []
    for row in stats:
        player = players_by_id[row["player_id"]]
        games_played = float(row["games_played"] or 0)
        wins = float(row["wins"] or 0)
        losses = float(row["losses"] or 0)
        win_points = float(row["win_point_wins"] or 0) + float(
            row["win_point_ties"] or 0
        )
        finish_points = float(row["finish_points"] or 0)
        raw_rank_score = compute_rank_score(
            points_total=finish_points,
            games_played=games_played,
        )
        rank_score = apply_vesting_to_rank_score(raw_rank_score, games_played)
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


def _default_standings_sort_key(row: PlayerRanking) -> tuple:
    return (
        -row.rank_score,
        -row.games_played,
        -row.finish_points,
        row.player.display_label.lower(),
    )


def _assign_ranks(rows: list[PlayerRanking]) -> list[PlayerRanking]:
    ordered = sorted(rows, key=_default_standings_sort_key)
    ranked: list[PlayerRanking] = []
    for index, row in enumerate(ordered, start=1):
        ranked.append(replace(row, rank=index))
    return ranked
