from __future__ import annotations

from leaderlodge.games.registry import get_game_type, score_direction_label
from leaderlodge.groups.models import Group
from leaderlodge.insights.tools.standings import query_player_detail
from leaderlodge.leaderboards.game_filters import LeaderboardGameFilters
from leaderlodge.leaderboards.period import (
    LeaderboardPeriod,
    available_leaderboard_periods,
)

MAX_RANK_HISTORY_YEARS = 15


def query_player_rank_history(
    group: Group,
    *,
    player_ids: list[int],
    game_type_code: str,
    years: list[int] | None = None,
    game_size: int | None = None,
    game_filters: LeaderboardGameFilters | None = None,
) -> dict:
    """Rank and rank_score for 2-5 players across one row per calendar year.

    Lets Ask answer "which years was X ahead of Y" in one tool call instead of
    a separate query_player_detail (or compare_players) call per year, which
    burns the tool-round budget fast for multi-year questions.
    """
    game_type = get_game_type(game_type_code)

    if years:
        resolved_years = sorted({int(year) for year in years})
    else:
        available_years, _ = available_leaderboard_periods(group, game_type_code)
        resolved_years = sorted(available_years)

    players_by_id: dict[int, dict] = {}
    history = []
    for year in resolved_years:
        period = LeaderboardPeriod(year=year)
        year_players = []
        for player_id in player_ids:
            detail = query_player_detail(
                group,
                player_id=player_id,
                game_type_code=game_type_code,
                period=period,
                game_size=game_size,
                game_filters=game_filters,
            )
            players_by_id.setdefault(
                player_id,
                {
                    "player_id": player_id,
                    "display_label": detail.get("display_label"),
                },
            )
            year_players.append(
                {
                    "player_id": player_id,
                    "display_label": detail.get("display_label"),
                    "has_games": detail.get("has_games", True),
                    "rank": detail.get("rank"),
                    "rank_score": detail.get("rank_score"),
                    "games_played": detail.get("games_played"),
                }
            )

        ranked = [
            row for row in year_players if row["has_games"] and row["rank"] is not None
        ]
        leader = None
        if len(ranked) >= 2:
            best_rank = min(row["rank"] for row in ranked)
            top_rows = [row for row in ranked if row["rank"] == best_rank]
            if len(top_rows) == 1:
                leader = {
                    "player_id": top_rows[0]["player_id"],
                    "display_label": top_rows[0]["display_label"],
                }

        history.append(
            {
                "year": year,
                "players": year_players,
                "leader": leader,
                "tied": len(ranked) >= 2 and leader is None,
            }
        )

    payload = {
        "game_type_code": game_type_code,
        "game_type_name": game_type.name,
        "score_direction": score_direction_label(game_type_code),
        "game_size": game_size,
        "years": resolved_years,
        "players": list(players_by_id.values()),
        "history": history,
    }
    if game_filters is not None and game_filters.is_active():
        from leaderlodge.games.features import game_features_response_payload

        payload.update(
            game_features_response_payload(
                game_filters.as_selections(),
                game_type_code=game_type_code,
            )
        )
    return payload
