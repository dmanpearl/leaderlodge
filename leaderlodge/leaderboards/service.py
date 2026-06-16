"""
Leaderboard ranking for a group.

Rankings are scoped by game type. A player who plays both dominos and backgammon
receives one PlayerRanking row per game type (e.g. david-dominos, david-backgammon).

Phase 1 ranks by wins within each game type. The ranking logic lives in this
module only and will evolve in place as requirements grow.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING

from django.conf import settings
from django.db.models import Q, Sum

from leaderlodge.games.registry import GAME_TYPES, get_game_type

if TYPE_CHECKING:
    from leaderlodge.groups.models import Group, GroupPlayer


@dataclass(frozen=True)
class PlayerRanking:
    """One player's standing for a single game type within a group."""

    player: GroupPlayer
    game_type_code: str
    game_type_name: str
    games_played: int
    wins: int
    win_pct: float
    rank: int


def get_player_rankings(
    group: Group,
    *,
    game_type_code: str | None = None,
    min_games: int | None = None,
) -> list[PlayerRanking]:
    """
    Return player rankings for a group.

    When game_type_code is set, only that game type is included.
    When game_type_code is None, all game types with recorded games are
    included. The same player may appear multiple times (once per game type).
    """
    if min_games is None:
        min_games = settings.MIN_GAMES_FOR_LEADERBOARD

    if game_type_code is not None:
        game_type_codes = [game_type_code]
    else:
        game_type_codes = _game_type_codes_for_group(group)

    rankings: list[PlayerRanking] = []
    for code in game_type_codes:
        rankings.extend(_rankings_for_game_type(group, code, min_games))

    return rankings


def _game_type_codes_for_group(group: Group) -> list[str]:
    from leaderlodge.games.models import Game

    codes = (
        Game.objects.filter(group=group)
        .values_list("game_type_code", flat=True)
        .distinct()
        .order_by("game_type_code")
    )
    return list(codes)


def _rankings_for_game_type(
    group: Group,
    game_type_code: str,
    min_games: int,
) -> list[PlayerRanking]:
    from leaderlodge.games.models import GameParticipantResult

    game_type = get_game_type(game_type_code)

    stats = (
        GameParticipantResult.objects.filter(
            game__group=group,
            game__game_type_code=game_type_code,
        )
        .values("player_id", "player__display_name")
        .annotate(
            games_played=Sum("game__double_weight"),
            wins=Sum(
                "game__double_weight",
                filter=Q(result=GameParticipantResult.Result.WIN),
            ),
        )
        .filter(games_played__gte=min_games)
        .order_by("-wins", "-games_played", "player__display_name")
    )

    from leaderlodge.groups.models import GroupPlayer

    rankings: list[PlayerRanking] = []
    for rank_index, row in enumerate(stats, start=1):
        player = GroupPlayer.objects.get(pk=row["player_id"])
        games_played = row["games_played"]
        wins = row["wins"]
        win_pct = (wins / games_played * 100) if games_played else 0.0
        rankings.append(
            PlayerRanking(
                player=player,
                game_type_code=game_type.code,
                game_type_name=game_type.name,
                games_played=games_played,
                wins=wins,
                win_pct=win_pct,
                rank=rank_index,
            )
        )

    return rankings


def get_player_stats(
    group: Group,
    player: GroupPlayer,
) -> dict[str, dict[str, int | float]]:
    """
    Basic stats keyed by game_type_code: games_played, wins, win_pct.
    """
    from leaderlodge.games.models import GameParticipantResult

    rows = (
        GameParticipantResult.objects.filter(game__group=group, player=player)
        .values("game__game_type_code")
        .annotate(
            games_played=Sum("game__double_weight"),
            wins=Sum(
                "game__double_weight",
                filter=Q(result=GameParticipantResult.Result.WIN),
            ),
        )
    )

    stats: dict[str, dict[str, int | float]] = defaultdict(
        lambda: {"games_played": 0, "wins": 0, "win_pct": 0.0}
    )
    for row in rows:
        code = row["game__game_type_code"]
        games_played = row["games_played"]
        wins = row["wins"]
        stats[code] = {
            "games_played": games_played,
            "wins": wins,
            "win_pct": (wins / games_played * 100) if games_played else 0.0,
        }

    for code in stats:
        game_type = GAME_TYPES.get(code)
        if game_type:
            stats[code]["game_type_name"] = game_type.name

    return dict(stats)
