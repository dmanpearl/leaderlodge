from __future__ import annotations

from django.db.models import Count, Q

from leaderlodge.games.list_stats import build_game_list_stats
from leaderlodge.games.models import Game
from leaderlodge.games.registry import get_game_type, score_direction_label
from leaderlodge.groups.models import Group, GroupPlayer
from leaderlodge.leaderboards.period import LeaderboardPeriod, filter_results_by_period


def _shared_table_games_qs(
    group: Group,
    *,
    game_type_code: str,
    player_ids: tuple[int, int],
    period: LeaderboardPeriod,
    game_size: int | None,
):
    qs = Game.objects.filter(group=group, game_type_code=game_type_code)
    if game_size is not None:
        qs = qs.filter(player_count=game_size)
    qs = filter_results_by_period(qs, period, game_prefix="")
    return qs.annotate(
        matched_players=Count(
            "participant_results__player",
            filter=Q(participant_results__player_id__in=player_ids),
            distinct=True,
        ),
    ).filter(matched_players=len(player_ids))


def _player_stats_row(row) -> dict:
    return {
        "player_id": row.player.pk,
        "display_label": row.player.display_label,
        "games_played": row.games_played,
        "wins": row.wins,
        "ties": row.ties,
        "losses": row.losses,
        "total_points": row.total_points,
        "max_score": row.max_score,
        "min_score": row.min_score,
    }


def query_head_to_head(
    group: Group,
    *,
    game_type_code: str,
    player_a_id: int,
    player_b_id: int,
    period: LeaderboardPeriod | None = None,
    game_size: int | None = None,
) -> dict:
    if player_a_id == player_b_id:
        return {"error": "Head-to-head requires two different players."}

    if period is None:
        period = LeaderboardPeriod.all_time()

    game_type = get_game_type(game_type_code)
    player_ids = (player_a_id, player_b_id)
    players_by_id = {
        player.pk: player
        for player in GroupPlayer.objects.filter(pk__in=player_ids).select_related(
            "linked_user"
        )
    }
    player_a = players_by_id.get(player_a_id)
    player_b = players_by_id.get(player_b_id)
    if player_a is None or player_b is None:
        return {"error": "One or both players not found in this group."}

    games_qs = _shared_table_games_qs(
        group,
        game_type_code=game_type_code,
        player_ids=player_ids,
        period=period,
        game_size=game_size,
    )
    stats = build_game_list_stats(games_qs=games_qs, game_type_code=game_type_code)
    if stats is None:
        return {
            "game_type_code": game_type_code,
            "game_type_name": game_type.name,
            "score_direction": score_direction_label(game_type_code),
            "game_size": game_size,
            "period": period.query_params() or {"all_time": True},
            "games_together": 0,
            "player_a": {
                "player_id": player_a.pk,
                "display_label": player_a.display_label,
                "games_played": 0,
                "wins": 0,
                "ties": 0,
                "losses": 0,
            },
            "player_b": {
                "player_id": player_b.pk,
                "display_label": player_b.display_label,
                "games_played": 0,
                "wins": 0,
                "ties": 0,
                "losses": 0,
            },
            "supports_loser": game_type.supports_loser,
        }

    stats_by_id = {row.player.pk: row for row in stats.players}
    row_a = stats_by_id.get(player_a_id)
    row_b = stats_by_id.get(player_b_id)

    def empty_row(player: GroupPlayer) -> dict:
        return {
            "player_id": player.pk,
            "display_label": player.display_label,
            "games_played": 0,
            "wins": 0,
            "ties": 0,
            "losses": 0,
        }

    return {
        "game_type_code": game_type_code,
        "game_type_name": game_type.name,
        "score_direction": score_direction_label(game_type_code),
        "game_size": game_size,
        "period": period.query_params() or {"all_time": True},
        "games_together": stats.total_games,
        "player_a": _player_stats_row(row_a) if row_a else empty_row(player_a),
        "player_b": _player_stats_row(row_b) if row_b else empty_row(player_b),
        "supports_loser": game_type.supports_loser,
    }
