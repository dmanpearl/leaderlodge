from __future__ import annotations

from leaderlodge.games.registry import get_game_type, score_direction_label
from leaderlodge.groups.models import Group
from leaderlodge.insights.tools.rate_display import add_outcome_display_fields
from leaderlodge.leaderboards.game_filters import LeaderboardGameFilters
from leaderlodge.leaderboards.period import LeaderboardPeriod
from leaderlodge.leaderboards.service import _standings_for_game_type
from leaderlodge.games.features import game_features_response_payload


def query_loss_leaders(
    group: Group,
    *,
    game_type_code: str,
    period: LeaderboardPeriod | None = None,
    game_size: int | None = None,
    game_filters: LeaderboardGameFilters | None = None,
    limit: int = 10,
) -> dict:
    if period is None:
        period = LeaderboardPeriod.all_time()

    game_type = get_game_type(game_type_code)
    if not game_type.supports_loser:
        return {
            "game_type_code": game_type_code,
            "game_type_name": game_type.name,
            "supports_loser": False,
            "error": (
                "This game type does not record explicit losses. "
                "Try query_placement_leaders for last-place finishes."
            ),
        }

    standings = _standings_for_game_type(
        group,
        game_type_code,
        period=period,
        game_size=game_size,
        game_filters=game_filters,
    )
    active = [row for row in standings if row.games_played > 0 and row.losses > 0]
    active.sort(key=lambda row: (-row.losses, row.player.display_label.lower()))

    leaders = []
    for rank, row in enumerate(active[:limit], start=1):
        games_played = round(row.games_played, 2)
        payload = {
            "rank": rank,
            "player_id": row.player.pk,
            "display_label": row.player.display_label,
            "games_played": games_played,
            "losses": round(row.losses, 2),
            "loss_pct": round(row.loss_pct, 1),
        }
        leaders.append(add_outcome_display_fields(payload, total=games_played))

    payload = {
        "game_type_code": game_type_code,
        "game_type_name": game_type.name,
        "score_direction": score_direction_label(game_type_code),
        "supports_loser": True,
        "game_size": game_size,
        "period": period.query_params() or {"all_time": True},
        "leaders": leaders,
    }
    if game_filters is not None and game_filters.is_active():
        payload.update(
            game_features_response_payload(
                game_filters.as_selections(),
                game_type_code=game_type_code,
            )
        )
    return payload
