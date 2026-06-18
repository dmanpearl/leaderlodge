from __future__ import annotations

from dataclasses import dataclass

from django.db.models import Count, Max, Min, Q, QuerySet, Sum

from leaderlodge.games.models import Game, GameParticipantResult
from leaderlodge.games.registry import GAME_TYPES, get_game_type
from leaderlodge.groups.models import GroupPlayer


@dataclass(frozen=True)
class PlayerListStats:
    player: GroupPlayer
    wins: int
    ties: int
    losses: int
    total_points: int
    max_score: int
    min_score: int


@dataclass(frozen=True)
class GameListStats:
    total_games: int
    show_losses: bool
    global_max_score: int | None
    global_min_score: int | None
    players: tuple[PlayerListStats, ...]


def build_game_list_stats(
    *,
    games_qs: QuerySet[Game],
    game_type_code: str,
) -> GameListStats | None:
    """
    Aggregate stats for the full filtered game queryset (not a paginated page).
    """
    if not games_qs.exists():
        return None

    total_games = games_qs.count()
    show_losses = (
        game_type_code in GAME_TYPES
        and get_game_type(game_type_code).supports_loser
    )

    results_qs = GameParticipantResult.objects.filter(game__in=games_qs)
    global_agg = results_qs.aggregate(
        global_max_score=Max("score"),
        global_min_score=Min("score"),
    )

    player_rows = (
        results_qs.values("player_id")
        .annotate(
            wins=Count("pk", filter=Q(result=GameParticipantResult.Result.WIN)),
            ties=Count("pk", filter=Q(result=GameParticipantResult.Result.TIE)),
            losses=Count("pk", filter=Q(result=GameParticipantResult.Result.LOSS)),
            total_points=Sum("score"),
            max_score=Max("score"),
            min_score=Min("score"),
        )
        .order_by("player_id")
    )

    player_ids = [row["player_id"] for row in player_rows]
    players_by_id = {
        player.pk: player
        for player in GroupPlayer.objects.filter(pk__in=player_ids).select_related(
            "linked_user"
        )
    }

    players: list[PlayerListStats] = []
    for row in player_rows:
        player = players_by_id[row["player_id"]]
        players.append(
            PlayerListStats(
                player=player,
                wins=row["wins"] or 0,
                ties=row["ties"] or 0,
                losses=row["losses"] or 0,
                total_points=row["total_points"] or 0,
                max_score=row["max_score"],
                min_score=row["min_score"],
            )
        )

    players.sort(key=lambda item: item.player.display_label.lower())

    return GameListStats(
        total_games=total_games,
        show_losses=show_losses,
        global_max_score=global_agg["global_max_score"],
        global_min_score=global_agg["global_min_score"],
        players=tuple(players),
    )
