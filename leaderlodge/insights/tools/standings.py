from __future__ import annotations

from datetime import date

from leaderlodge.games.registry import (
    get_game_type,
    score_direction_label,
    scoring_interpretation_note,
)
from leaderlodge.groups.models import Group, GroupPlayer
from leaderlodge.insights.tools.rate_display import (
    add_avg_score_display_fields,
    add_outcome_display_fields,
)
from leaderlodge.leaderboards.game_filters import LeaderboardGameFilters
from leaderlodge.leaderboards.period import LeaderboardPeriod
from leaderlodge.leaderboards.ranking import compute_percentage
from leaderlodge.leaderboards.service import (
    get_player_rank_detail,
    get_player_rankings,
)
from leaderlodge.games.features import feature_catalog_for_game_type, game_features_response_payload


def _attach_game_features(
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
    location_ids: list[int] | None = None,
    game_filters: LeaderboardGameFilters | None = None,
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
        location_ids=location_ids,
        game_filters=game_filters,
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
    if location_ids is not None:
        payload["location_ids"] = list(location_ids)
    return _attach_game_features(
        payload,
        game_type_code=game_type_code,
        game_filters=game_filters,
    )


def query_location_leaderboard(
    group: Group,
    *,
    game_type_code: str,
    location_id: int,
    location_name: str,
    period: LeaderboardPeriod | None = None,
    game_size: int | None = None,
    game_filters: LeaderboardGameFilters | None = None,
    limit: int = 10,
) -> dict:
    payload = query_leaderboard(
        group,
        game_type_code=game_type_code,
        period=period,
        game_size=game_size,
        location_id=location_id,
        game_filters=game_filters,
        limit=limit,
    )
    payload["location_name"] = location_name
    return payload


def query_region_leaderboard(
    group: Group,
    *,
    game_type_code: str,
    city: str | None = None,
    state: str | None = None,
    exclude: bool = False,
    period: LeaderboardPeriod | None = None,
    game_size: int | None = None,
    game_filters: LeaderboardGameFilters | None = None,
    limit: int = 10,
) -> dict:
    from leaderlodge.insights.tools.region import (
        region_match_payload,
        resolve_region_locations,
    )

    match = resolve_region_locations(group, city=city, state=state, exclude=exclude)
    payload = query_leaderboard(
        group,
        game_type_code=game_type_code,
        period=period,
        game_size=game_size,
        location_ids=match.location_ids,
        game_filters=game_filters,
        limit=limit,
    )
    payload.update(region_match_payload(match))
    return payload


def query_play_locations(
    group: Group,
    *,
    game_type_code: str,
    city: str | None = None,
    state: str | None = None,
    exclude: bool = False,
    period: LeaderboardPeriod | None = None,
    game_size: int | None = None,
    limit: int = 10,
) -> dict:
    from django.db.models import Count

    from leaderlodge.games.models import Game
    from leaderlodge.insights.tools.region import (
        region_match_payload,
        resolve_region_locations,
    )
    from leaderlodge.leaderboards.period import filter_results_by_period

    if period is None:
        period = LeaderboardPeriod.all_time()

    game_type = get_game_type(game_type_code)
    games_qs = Game.objects.filter(
        group=group,
        game_type_code=game_type_code,
        location_id__isnull=False,
    )
    if game_size is not None:
        games_qs = games_qs.filter(player_count=game_size)
    games_qs = filter_results_by_period(games_qs, period, game_prefix="")

    region_payload: dict = {}
    if city or state:
        match = resolve_region_locations(group, city=city, state=state, exclude=exclude)
        games_qs = games_qs.filter(location_id__in=match.location_ids)
        region_payload = region_match_payload(match)

    rows = list(
        games_qs.values(
            "location_id",
            "location__name",
            "location__city",
            "location__state",
        )
        .annotate(games_played=Count("id"))
        .order_by("-games_played", "location__name")[:limit]
    )

    payload = {
        "game_type_code": game_type_code,
        "game_type_name": game_type.name,
        "period": period.query_params() or {"all_time": True},
        "game_size": game_size,
        "locations": [
            {
                "location_id": row["location_id"],
                "name": row["location__name"],
                "city": row["location__city"] or None,
                "state": row["location__state"] or None,
                "games_played": row["games_played"],
            }
            for row in rows
        ],
    }
    payload.update(region_payload)
    return payload


_PLAYER_LOCATION_GROUP_BY = frozenset({"state", "city", "venue"})


def query_player_play_locations(
    group: Group,
    *,
    player_id: int,
    game_type_code: str,
    group_by: str = "state",
    period: LeaderboardPeriod | None = None,
    game_size: int | None = None,
    limit: int = 20,
) -> dict:
    """Count one player's games grouped by state, city, or venue."""
    from django.db.models import Count

    from leaderlodge.games.models import Game
    from leaderlodge.groups.teams import results_queryset_for_player_credit
    from leaderlodge.insights.tools.region import state_display_label
    from leaderlodge.leaderboards.period import filter_results_by_period

    group_by = str(group_by or "state").strip().lower()
    if group_by not in _PLAYER_LOCATION_GROUP_BY:
        raise ValueError("group_by must be state, city, or venue.")

    if period is None:
        period = LeaderboardPeriod.all_time()

    player = group.players.filter(pk=player_id).select_related("linked_user").first()
    if player is None:
        return {"error": "Player not found in this group."}

    game_type = get_game_type(game_type_code)
    results_qs = results_queryset_for_player_credit(player).filter(
        game__group=group,
        game__game_type_code=game_type_code,
    )
    if game_size is not None:
        results_qs = results_qs.filter(game__player_count=game_size)
    results_qs = filter_results_by_period(results_qs, period)

    game_ids = list(results_qs.values_list("game_id", flat=True).distinct())
    total_games = len(game_ids)
    games_qs = Game.objects.filter(pk__in=game_ids)
    games_without_location = games_qs.filter(location_id__isnull=True).count()
    located_qs = games_qs.filter(location_id__isnull=False)

    rows: list[dict] = []
    unknown_games = 0

    if group_by == "state":
        aggregated = list(
            located_qs.values("location__state")
            .annotate(games_played=Count("id"))
            .order_by("-games_played", "location__state")
        )
        for row in aggregated:
            raw_state = (row["location__state"] or "").strip()
            count = row["games_played"]
            if not raw_state:
                unknown_games += count
                rows.append(
                    {
                        "state": None,
                        "label": "(unknown / blank state)",
                        "games_played": count,
                    }
                )
            else:
                rows.append(
                    {
                        "state": raw_state,
                        "label": state_display_label(raw_state),
                        "games_played": count,
                    }
                )
    elif group_by == "city":
        aggregated = list(
            located_qs.values("location__city", "location__state")
            .annotate(games_played=Count("id"))
            .order_by("-games_played", "location__city", "location__state")
        )
        for row in aggregated:
            raw_city = (row["location__city"] or "").strip()
            raw_state = (row["location__state"] or "").strip()
            count = row["games_played"]
            if not raw_city:
                unknown_games += count
                label = "(unknown / blank city)"
                if raw_state:
                    label = f"(unknown city), {state_display_label(raw_state)}"
                rows.append(
                    {
                        "city": None,
                        "state": raw_state or None,
                        "label": label,
                        "games_played": count,
                    }
                )
            else:
                label = raw_city
                if raw_state:
                    label = f"{raw_city}, {state_display_label(raw_state)}"
                rows.append(
                    {
                        "city": raw_city,
                        "state": raw_state or None,
                        "label": label,
                        "games_played": count,
                    }
                )
    else:
        aggregated = list(
            located_qs.values(
                "location_id",
                "location__name",
                "location__city",
                "location__state",
            )
            .annotate(games_played=Count("id"))
            .order_by("-games_played", "location__name")
        )
        for row in aggregated:
            raw_city = (row["location__city"] or "").strip()
            raw_state = (row["location__state"] or "").strip()
            rows.append(
                {
                    "location_id": row["location_id"],
                    "name": row["location__name"],
                    "city": raw_city or None,
                    "state": raw_state or None,
                    "games_played": row["games_played"],
                }
            )

    if games_without_location:
        unknown_games += games_without_location
        if group_by == "venue":
            rows.append(
                {
                    "location_id": None,
                    "name": "(no location)",
                    "city": None,
                    "state": None,
                    "games_played": games_without_location,
                }
            )
        elif group_by == "city":
            matched = next(
                (r for r in rows if r.get("city") is None and not r.get("state")),
                None,
            )
            if matched is None:
                rows.append(
                    {
                        "city": None,
                        "state": None,
                        "label": "(unknown / blank city)",
                        "games_played": games_without_location,
                    }
                )
            else:
                matched["games_played"] += games_without_location
        else:
            matched = next((r for r in rows if r.get("state") is None), None)
            if matched is None:
                rows.append(
                    {
                        "state": None,
                        "label": "(unknown / blank state)",
                        "games_played": games_without_location,
                    }
                )
            else:
                matched["games_played"] += games_without_location

    rows.sort(
        key=lambda item: (
            -(item["games_played"]),
            str(item.get("label") or item.get("name") or ""),
        )
    )
    rows = rows[:limit]

    known_games = total_games - unknown_games
    coverage_note = None
    if unknown_games > 0:
        coverage_note = (
            f"{unknown_games} of {total_games} games have blank or missing "
            f"{'venue' if group_by == 'venue' else group_by} geo. Do not treat "
            "unknown games as belonging to any specific state or city."
        )

    return {
        "player_id": player.pk,
        "display_label": player.display_label,
        "game_type_code": game_type_code,
        "game_type_name": game_type.name,
        "group_by": group_by,
        "period": period.query_params() or {"all_time": True},
        "game_size": game_size,
        "total_games": total_games,
        "games_with_known_region": max(known_games, 0),
        "games_unknown_region": unknown_games,
        "games_without_location": games_without_location,
        "rows": rows,
        **({"coverage_note": coverage_note} if coverage_note else {}),
    }


def query_date_range_leaderboard(
    group: Group,
    *,
    game_type_code: str,
    start_date: date,
    end_date: date,
    period_preset: str | None = None,
    game_size: int | None = None,
    game_filters: LeaderboardGameFilters | None = None,
    limit: int = 10,
) -> dict:
    period = LeaderboardPeriod(
        start_date=start_date,
        end_date=end_date,
        preset=period_preset,
    )
    payload = query_leaderboard(
        group,
        game_type_code=game_type_code,
        period=period,
        game_size=game_size,
        game_filters=game_filters,
        limit=limit,
    )
    payload["start_date"] = start_date.isoformat()
    payload["end_date"] = end_date.isoformat()
    return payload


def query_player_detail(
    group: Group,
    *,
    player_id: int,
    game_type_code: str,
    period: LeaderboardPeriod | None = None,
    game_size: int | None = None,
    game_filters: LeaderboardGameFilters | None = None,
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
        game_filters=game_filters,
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
    return _attach_game_features(
        add_avg_score_display_fields(payload),
        game_type_code=game_type_code,
        game_filters=game_filters,
    )


def list_game_types(group: Group) -> dict:
    from leaderlodge.games.models import Game

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
                "features": feature_catalog_for_game_type(code),
            }
            for code in codes
        ],
    }
