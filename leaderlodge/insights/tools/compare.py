from __future__ import annotations

from leaderlodge.games.registry import get_game_type, score_direction_label
from leaderlodge.groups.models import Group
from leaderlodge.insights.tools.standings import query_player_detail
from leaderlodge.leaderboards.game_filters import LeaderboardGameFilters
from leaderlodge.leaderboards.period import LeaderboardPeriod


def compare_players(
    group: Group,
    *,
    player_ids: list[int],
    game_type_code: str,
    period: LeaderboardPeriod | None = None,
    game_size: int | None = None,
    game_filters: LeaderboardGameFilters | None = None,
) -> dict:
    if period is None:
        period = LeaderboardPeriod.all_time()

    game_type = get_game_type(game_type_code)
    players = []
    for player_id in player_ids:
        detail = query_player_detail(
            group,
            player_id=player_id,
            game_type_code=game_type_code,
            period=period,
            game_size=game_size,
            game_filters=game_filters,
        )
        players.append(detail)

    payload = {
        "game_type_code": game_type_code,
        "game_type_name": game_type.name,
        "score_direction": score_direction_label(game_type_code),
        "game_size": game_size,
        "period": period.query_params() or {"all_time": True},
        "players": players,
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
