from __future__ import annotations

from django.db.models import Count, Q

from leaderlodge.games.list_stats import build_game_list_stats
from leaderlodge.games.models import Game
from leaderlodge.games.registry import (
    get_game_type,
    score_direction_label,
    scoring_interpretation_note,
)
from leaderlodge.groups.models import Group, GroupPlayer
from leaderlodge.insights.tools.rate_display import (
    add_outcome_display_fields,
    add_points_display_fields,
)
from leaderlodge.leaderboards.game_filters import LeaderboardGameFilters
from leaderlodge.leaderboards.period import LeaderboardPeriod, filter_results_by_period
from leaderlodge.leaderboards.ranking import compute_percentage
from leaderlodge.leaderboards.service import get_player_rank_detail
from leaderlodge.games.features import (
    apply_feature_selections_to_games_qs,
    game_features_response_payload,
)


def _attach_head_to_head_features(
    payload: dict,
    *,
    game_type_code: str,
    game_filters: LeaderboardGameFilters | None,
) -> dict:
    if game_filters is not None and game_filters.is_active():
        payload.update(
            game_features_response_payload(
                game_filters.as_selections(),
                game_type_code=game_type_code,
            )
        )
    return payload


def _overall_rank_fields(
    group: Group,
    player: GroupPlayer,
    *,
    game_type_code: str,
    period: LeaderboardPeriod,
    game_size: int | None,
    game_filters: LeaderboardGameFilters | None = None,
) -> dict:
    detail = get_player_rank_detail(
        group,
        player,
        game_type_code=game_type_code,
        period=period,
        game_size=game_size,
        game_filters=game_filters,
    )
    if detail is None:
        return {"rank": None, "rank_score": None}
    return {
        "rank": detail.ranking.rank,
        "rank_score": round(detail.ranking.rank_score, 2),
    }


def _shared_table_games_qs(
    group: Group,
    *,
    game_type_code: str,
    player_ids: tuple[int, int],
    period: LeaderboardPeriod,
    game_size: int | None,
    game_filters: LeaderboardGameFilters | None = None,
):
    qs = Game.objects.filter(group=group, game_type_code=game_type_code)
    if game_size is not None:
        qs = qs.filter(player_count=game_size)
    qs = filter_results_by_period(qs, period, game_prefix="")
    if game_filters is not None and game_filters.is_active():
        qs = apply_feature_selections_to_games_qs(
            qs,
            game_filters.as_selections(),
            game_type_code=game_type_code,
        )
    return qs.annotate(
        matched_players=Count(
            "participant_results__player",
            filter=Q(participant_results__player_id__in=player_ids),
            distinct=True,
        ),
    ).filter(matched_players=len(player_ids))


def _player_stats_row(row) -> dict:
    games_played = row.games_played
    win_pct = round(compute_percentage(row.wins, games_played), 1)
    tie_pct = round(compute_percentage(row.ties, games_played), 1)
    loss_pct = round(compute_percentage(row.losses, games_played), 1)
    payload = {
        "player_id": row.player.pk,
        "display_label": row.player.display_label,
        "games_played": games_played,
        "wins": row.wins,
        "win_pct": win_pct,
        "ties": row.ties,
        "tie_pct": tie_pct,
        "losses": row.losses,
        "loss_pct": loss_pct,
        "total_points": row.total_points,
        "max_score": row.max_score,
        "min_score": row.min_score,
    }
    payload = add_outcome_display_fields(payload, total=games_played)
    return add_points_display_fields(payload)


def _empty_player_row(player: GroupPlayer) -> dict:
    payload = {
        "player_id": player.pk,
        "display_label": player.display_label,
        "games_played": 0,
        "wins": 0,
        "win_pct": 0.0,
        "ties": 0,
        "tie_pct": 0.0,
        "losses": 0,
        "loss_pct": 0.0,
    }
    return add_outcome_display_fields(payload, total=0)


def query_head_to_head(
    group: Group,
    *,
    game_type_code: str,
    player_a_id: int,
    player_b_id: int,
    period: LeaderboardPeriod | None = None,
    game_size: int | None = None,
    game_filters: LeaderboardGameFilters | None = None,
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
        game_filters=game_filters,
    )
    stats = build_game_list_stats(games_qs=games_qs, game_type_code=game_type_code)
    if stats is None:
        player_a_row = _empty_player_row(player_a)
        player_b_row = _empty_player_row(player_b)
        player_a_row.update(
            _overall_rank_fields(
                group,
                player_a,
                game_type_code=game_type_code,
                period=period,
                game_size=game_size,
                game_filters=game_filters,
            )
        )
        player_b_row.update(
            _overall_rank_fields(
                group,
                player_b,
                game_type_code=game_type_code,
                period=period,
                game_size=game_size,
                game_filters=game_filters,
            )
        )
        return _attach_head_to_head_features(
            _head_to_head_payload(
                game_type_code=game_type_code,
                game_type_name=game_type.name,
                game_size=game_size,
                period=period,
                games_together=0,
                player_a=player_a_row,
                player_b=player_b_row,
                supports_loser=game_type.supports_loser,
            ),
            game_type_code=game_type_code,
            game_filters=game_filters,
        )

    stats_by_id = {row.player.pk: row for row in stats.players}
    row_a = stats_by_id.get(player_a_id)
    row_b = stats_by_id.get(player_b_id)

    player_a_row = _player_stats_row(row_a) if row_a else _empty_player_row(player_a)
    player_b_row = _player_stats_row(row_b) if row_b else _empty_player_row(player_b)
    player_a_row.update(
        _overall_rank_fields(
            group,
            player_a,
            game_type_code=game_type_code,
            period=period,
            game_size=game_size,
            game_filters=game_filters,
        )
    )
    player_b_row.update(
        _overall_rank_fields(
            group,
            player_b,
            game_type_code=game_type_code,
            period=period,
            game_size=game_size,
            game_filters=game_filters,
        )
    )

    return _attach_head_to_head_features(
        _head_to_head_payload(
            game_type_code=game_type_code,
            game_type_name=game_type.name,
            game_size=game_size,
            period=period,
            games_together=stats.total_games,
            player_a=player_a_row,
            player_b=player_b_row,
            supports_loser=game_type.supports_loser,
        ),
        game_type_code=game_type_code,
        game_filters=game_filters,
    )


def _head_to_head_payload(
    *,
    game_type_code: str,
    game_type_name: str,
    game_size: int | None,
    period: LeaderboardPeriod,
    **extra: object,
) -> dict:
    payload = {
        "game_type_code": game_type_code,
        "game_type_name": game_type_name,
        "score_direction": score_direction_label(game_type_code),
        "game_size": game_size,
        "period": period.query_params() or {"all_time": True},
        **extra,
    }
    note = scoring_interpretation_note(game_type_code)
    if note is not None:
        payload["scoring_note"] = note
    return payload
