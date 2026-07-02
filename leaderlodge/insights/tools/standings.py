from __future__ import annotations

from datetime import date

from leaderlodge.games.models import GameParticipantResult
from leaderlodge.games.registry import (
    ScoreDirection,
    get_game_type,
    score_direction_label,
    scoring_interpretation_note,
)
from leaderlodge.groups.models import Group, GroupPlayer
from leaderlodge.insights.tools.rate_display import (
    add_avg_score_display_fields,
    add_outcome_display_fields,
)
from leaderlodge.leaderboards.period import (
    LeaderboardPeriod,
    filter_results_by_date_range,
)
from leaderlodge.leaderboards.ranking import compute_percentage
from leaderlodge.leaderboards.service import (
    _assign_ranks,
    _standings_for_game_type,
    get_player_rank_detail,
    get_player_rankings,
)


def _ranking_row(row) -> dict:
    return {
        "player_id": row.player.pk,
        "display_label": row.player.display_label,
        "rank": row.rank,
        "rank_score": round(row.rank_score, 2),
        "games_played": round(row.games_played, 2),
        "wins": round(row.wins, 2),
        "win_pct": round(row.win_pct, 1),
    }


def query_leaderboard(
    group: Group,
    *,
    game_type_code: str,
    period: LeaderboardPeriod | None = None,
    game_size: int | None = None,
    location_id: int | None = None,
    limit: int = 10,
) -> dict:
    if period is None:
        period = LeaderboardPeriod.all_time()

    game_type = get_game_type(game_type_code)
    rankings = get_player_rankings(
        group,
        game_type_code=game_type_code,
        period=period,
        game_size=game_size,
        location_id=location_id,
    )
    payload = {
        "game_type_code": game_type_code,
        "game_type_name": game_type.name,
        "score_direction": score_direction_label(game_type_code),
        "game_size": game_size,
        "period": period.query_params() or {"all_time": True},
        "rankings": [_ranking_row(row) for row in rankings[:limit]],
    }
    if location_id is not None:
        payload["location_id"] = location_id
    return payload


def query_location_leaderboard(
    group: Group,
    *,
    game_type_code: str,
    location_id: int,
    location_name: str,
    period: LeaderboardPeriod | None = None,
    game_size: int | None = None,
    limit: int = 10,
) -> dict:
    payload = query_leaderboard(
        group,
        game_type_code=game_type_code,
        period=period,
        game_size=game_size,
        location_id=location_id,
        limit=limit,
    )
    payload["location_name"] = location_name
    return payload


def query_date_range_leaderboard(
    group: Group,
    *,
    game_type_code: str,
    start_date: date,
    end_date: date,
    game_size: int | None = None,
    limit: int = 10,
) -> dict:
    game_type = get_game_type(game_type_code)
    results_qs = GameParticipantResult.objects.filter(
        game__group=group,
        game__game_type_code=game_type_code,
    )
    if game_size is not None:
        results_qs = results_qs.filter(game__player_count=game_size)
    results_qs = filter_results_by_date_range(
        results_qs,
        start_date=start_date,
        end_date=end_date,
    )

    # Any filtered period disables vesting; year is arbitrary here.
    period = LeaderboardPeriod(year=start_date.year)
    standings = _standings_for_game_type(
        group,
        game_type_code,
        period=period,
        results_qs=results_qs,
    )
    active = [row for row in standings if row.games_played > 0]
    low_wins = game_type.score_direction == ScoreDirection.LOW_WINS
    rankings = _assign_ranks(active, low_wins=low_wins)

    return {
        "game_type_code": game_type_code,
        "game_type_name": game_type.name,
        "score_direction": score_direction_label(game_type_code),
        "game_size": game_size,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "period": {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
        },
        "rankings": [_ranking_row(row) for row in rankings[:limit]],
    }


def query_player_detail(
    group: Group,
    *,
    player_id: int,
    game_type_code: str,
    period: LeaderboardPeriod | None = None,
    game_size: int | None = None,
) -> dict:
    if period is None:
        period = LeaderboardPeriod.all_time()

    player = group.players.filter(pk=player_id).select_related("linked_user").first()
    if player is None:
        return {"error": "Player not found in this group."}

    detail = get_player_rank_detail(
        group,
        player,
        game_type_code=game_type_code,
        period=period,
        game_size=game_size,
    )
    if detail is None:
        return {
            "player_id": player.pk,
            "display_label": player.display_label,
            "game_type_code": game_type_code,
            "has_games": False,
        }

    game_type = get_game_type(game_type_code)

    def _score_highlight(item) -> dict | None:
        if item is None:
            return None
        return {"score": item.score, "played_on": item.played_on.isoformat()}

    games_played = round(detail.ranking.games_played, 2)
    wins = round(detail.ranking.wins, 2)
    win_pct = round(detail.ranking.win_pct, 1)
    losses = round(detail.ranking.losses, 2)
    loss_pct = round(detail.ranking.loss_pct, 1)
    ties = detail.tie_count
    tie_pct = round(
        compute_percentage(detail.tie_count, detail.ranking.games_played), 1
    )

    payload = {
        "player_id": player.pk,
        "display_label": player.display_label,
        "game_type_code": game_type_code,
        "game_type_name": game_type.name,
        "score_direction": score_direction_label(game_type_code),
        **(
            {"scoring_note": note}
            if (note := scoring_interpretation_note(game_type_code)) is not None
            else {}
        ),
        "game_size": game_size,
        "period": period.query_params() or {"all_time": True},
        "rank": detail.ranking.rank,
        "rank_score": round(detail.ranking.rank_score, 2),
        "games_played": games_played,
        "wins": wins,
        "win_pct": win_pct,
        "losses": losses,
        "loss_pct": loss_pct,
        "ties": ties,
        "tie_pct": tie_pct,
        "average_field_size": round(detail.average_field_size, 1),
        "average_score": (
            round(detail.average_score, 1) if detail.average_score is not None else None
        ),
        "first_game_date": (
            detail.first_game_date.isoformat() if detail.first_game_date else None
        ),
        "last_game_date": (
            detail.last_game_date.isoformat() if detail.last_game_date else None
        ),
        "date_range_label": detail.date_range_label,
        "podium_count": detail.podium_count,
        "podium_pct": round(detail.podium_pct, 1),
        "best_score": _score_highlight(detail.best_score),
        "worst_score": _score_highlight(detail.worst_score),
        "placements": [
            {
                "placement": item.placement,
                "label": item.label,
                "weighted_count": round(item.weighted_count, 2),
                "count_pct": round(item.count_pct, 1),
            }
            for item in detail.placements
        ],
        "supports_loser": game_type.supports_loser,
    }
    payload = add_outcome_display_fields(payload, total=games_played)
    return add_avg_score_display_fields(payload)


def list_game_types(group: Group) -> dict:
    from leaderlodge.games.models import Game
    from leaderlodge.games.registry import get_game_type

    codes = list(
        Game.objects.filter(group=group)
        .values_list("game_type_code", flat=True)
        .distinct()
        .order_by("game_type_code")
    )
    return {
        "group_id": group.pk,
        "group_name": group.name,
        "game_types": [
            {
                "code": code,
                "name": get_game_type(code).name,
                "score_direction": score_direction_label(code),
            }
            for code in codes
        ],
    }
