from __future__ import annotations

from datetime import date, timedelta

from django.db.models import Q, Sum

from leaderlodge.games.models import GameParticipantResult
from leaderlodge.games.registry import ScoreDirection, get_game_type
from leaderlodge.games.standings import standings_weight_expression
from leaderlodge.groups.models import Group, GroupPlayer
from leaderlodge.leaderboards.period import LeaderboardPeriod
from leaderlodge.leaderboards.ranking import compute_rank_score
from leaderlodge.leaderboards.service import (
    _finish_points_by_player,
    get_player_rankings,
)


def query_rank_trends(
    group: Group,
    *,
    game_type_code: str,
    days: int = 90,
    game_size: int | None = None,
    limit: int = 10,
) -> dict:
    game_type = get_game_type(game_type_code)
    low_wins = game_type.score_direction == ScoreDirection.LOW_WINS
    today = date.today()
    recent_start = today - timedelta(days=days)
    prior_start = today - timedelta(days=days * 2)

    base_qs = GameParticipantResult.objects.filter(
        game__group=group,
        game__game_type_code=game_type_code,
    )
    if game_size is not None:
        base_qs = base_qs.filter(game__player_count=game_size)

    recent_qs = base_qs.filter(game__played_on__gte=recent_start)
    prior_qs = base_qs.filter(
        Q(game__played_on__gte=prior_start) & Q(game__played_on__lt=recent_start)
    )

    recent_points = _finish_points_by_player(recent_qs, low_wins=low_wins)
    prior_points = _finish_points_by_player(prior_qs, low_wins=low_wins)
    recent_games = _weighted_games_by_player(recent_qs)
    prior_games = _weighted_games_by_player(prior_qs)

    player_ids = set(recent_points) | set(prior_points)
    players_by_id = {
        player.pk: player
        for player in GroupPlayer.objects.filter(pk__in=player_ids).select_related(
            "linked_user"
        )
    }

    trends = []
    for player_id in player_ids:
        recent_gp = recent_games.get(player_id, 0.0)
        prior_gp = prior_games.get(player_id, 0.0)
        if recent_gp <= 0 or prior_gp <= 0:
            continue
        recent_score = compute_rank_score(
            points_total=recent_points.get(player_id, 0.0),
            games_played=recent_gp,
        )
        prior_score = compute_rank_score(
            points_total=prior_points.get(player_id, 0.0),
            games_played=prior_gp,
        )
        player = players_by_id.get(player_id)
        if player is None:
            continue
        trends.append(
            {
                "player_id": player.pk,
                "display_label": player.display_label,
                "recent_rank_score": round(recent_score, 2),
                "prior_rank_score": round(prior_score, 2),
                "improvement": round(recent_score - prior_score, 2),
                "recent_games": round(recent_gp, 2),
                "prior_games": round(prior_gp, 2),
            }
        )

    trends.sort(key=lambda row: row["improvement"], reverse=True)
    return {
        "game_type_code": game_type_code,
        "game_type_name": game_type.name,
        "game_size": game_size,
        "days": days,
        "recent_window_start": recent_start.isoformat(),
        "prior_window_start": prior_start.isoformat(),
        "prior_window_end": recent_start.isoformat(),
        "players": trends[:limit],
    }


def query_month_leaders(
    group: Group,
    *,
    game_type_code: str,
    month: int,
    year: int | None = None,
    game_size: int | None = None,
    metric: str = "rank_score",
    limit: int = 10,
) -> dict:
    game_type = get_game_type(game_type_code)

    if year is not None:
        period = LeaderboardPeriod(year=year, month=month)
        rankings = get_player_rankings(
            group,
            game_type_code=game_type_code,
            period=period,
            game_size=game_size,
        )
        leaders = _leaders_from_rankings(rankings, metric=metric, limit=limit)
        return {
            "game_type_code": game_type_code,
            "game_type_name": game_type.name,
            "month": month,
            "year": year,
            "game_size": game_size,
            "metric": metric,
            "leaders": leaders,
        }

    results_qs = GameParticipantResult.objects.filter(
        game__group=group,
        game__game_type_code=game_type_code,
        game__played_on__month=month,
    )
    if game_size is not None:
        results_qs = results_qs.filter(game__player_count=game_size)

    low_wins = game_type.score_direction == ScoreDirection.LOW_WINS
    finish_points = _finish_points_by_player(results_qs, low_wins=low_wins)
    games_by_player = _weighted_games_by_player(results_qs)
    rows = []
    for player_id, points in finish_points.items():
        games_played = games_by_player.get(player_id, 0.0)
        if games_played <= 0:
            continue
        score = compute_rank_score(points_total=points, games_played=games_played)
        wins = _weighted_wins_for_player(results_qs.filter(player_id=player_id))
        rows.append(
            {
                "player_id": player_id,
                "rank_score": score,
                "games_played": games_played,
                "wins": wins,
            }
        )

    metric_key = {
        "rank_score": lambda row: row["rank_score"],
        "wins": lambda row: row["wins"],
        "games_played": lambda row: row["games_played"],
    }.get(metric, lambda row: row["rank_score"])
    rows.sort(key=metric_key, reverse=True)

    players_by_id = {
        player.pk: player
        for player in GroupPlayer.objects.filter(
            pk__in=[row["player_id"] for row in rows[:limit]]
        ).select_related("linked_user")
    }
    leaders = []
    for row in rows[:limit]:
        player = players_by_id.get(row["player_id"])
        if player is None:
            continue
        leaders.append(
            {
                "player_id": player.pk,
                "display_label": player.display_label,
                "rank_score": round(row["rank_score"], 2),
                "wins": round(row["wins"], 2),
                "games_played": round(row["games_played"], 2),
            }
        )

    return {
        "game_type_code": game_type_code,
        "game_type_name": game_type.name,
        "month": month,
        "year": None,
        "game_size": game_size,
        "metric": metric,
        "leaders": leaders,
    }


def _leaders_from_rankings(rankings, *, metric: str, limit: int) -> list[dict]:
    metric_key = {
        "rank_score": lambda row: row.rank_score,
        "wins": lambda row: row.wins,
        "games_played": lambda row: row.games_played,
    }.get(metric, lambda row: row.rank_score)
    sorted_rows = sorted(rankings, key=metric_key, reverse=True)
    return [
        {
            "player_id": row.player.pk,
            "display_label": row.player.display_label,
            "rank": row.rank,
            "rank_score": round(row.rank_score, 2),
            "wins": round(row.wins, 2),
            "games_played": round(row.games_played, 2),
        }
        for row in sorted_rows[:limit]
    ]


def _weighted_games_by_player(results_qs) -> dict[int, float]:
    weight = standings_weight_expression()
    rows = results_qs.values("player_id").annotate(games_played=Sum(weight))
    return {row["player_id"]: float(row["games_played"] or 0) for row in rows}


def _weighted_wins_for_player(results_qs) -> float:
    from leaderlodge.games.models import GameParticipantResult

    weight = standings_weight_expression()
    value = (
        results_qs.filter(result=GameParticipantResult.Result.WIN)
        .aggregate(total=Sum(weight))
        .get("total")
    )
    return float(value or 0)
