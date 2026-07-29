from __future__ import annotations

from leaderlodge.games.registry import (
    get_game_type,
    score_direction_label,
    scoring_interpretation_note,
)
from leaderlodge.groups.models import Group
from leaderlodge.groups.teams import (
    PLAYER_TYPE_PEOPLE,
    PLAYER_TYPE_TEAM,
    team_member_players,
)
from leaderlodge.insights.tools.rate_display import add_outcome_display_fields
from leaderlodge.insights.tools.standings import _ranking_row
from leaderlodge.leaderboards.game_filters import LeaderboardGameFilters
from leaderlodge.leaderboards.period import LeaderboardPeriod
from leaderlodge.leaderboards.service import get_player_rankings
from leaderlodge.games.features import game_features_response_payload

MAX_TEAM_SIZE = 2


def _duo_team_row(row) -> dict | None:
    if not row.player.is_team:
        return None
    members = team_member_players(row.player)
    if len(members) != MAX_TEAM_SIZE:
        return None
    payload = {
        **_ranking_row(row),
        "member_player_ids": [member.pk for member in members],
        "member_labels": [member.display_label for member in members],
    }
    add_outcome_display_fields(
        payload,
        total=row.games_played,
        outcomes=(("wins", "win_pct", "wins_display"),),
    )
    return payload


def query_team_pairings(
    group: Group,
    *,
    game_type_code: str,
    period: LeaderboardPeriod | None = None,
    game_size: int | None = None,
    game_filters: LeaderboardGameFilters | None = None,
    limit: int = 10,
) -> dict:
    """Observed two-player teams and individual standings for pairing questions."""
    if period is None:
        period = LeaderboardPeriod.all_time()

    game_type = get_game_type(game_type_code)
    individual_rankings = get_player_rankings(
        group,
        game_type_code=game_type_code,
        period=period,
        game_size=game_size,
        player_type=PLAYER_TYPE_PEOPLE,
        game_filters=game_filters,
    )
    team_rankings = get_player_rankings(
        group,
        game_type_code=game_type_code,
        period=period,
        game_size=game_size,
        player_type=PLAYER_TYPE_TEAM,
        game_filters=game_filters,
    )

    observed_duo_teams: list[dict] = []
    for row in team_rankings:
        duo_row = _duo_team_row(row)
        if duo_row is not None:
            observed_duo_teams.append(duo_row)

    observed_duo_teams.sort(
        key=lambda row: (
            -float(row["rank_score"]),
            -float(row["wins"]),
            -float(row["games_played"]),
        )
    )

    payload = {
        "game_type_code": game_type_code,
        "game_type_name": game_type.name,
        "score_direction": score_direction_label(game_type_code),
        "team_size": MAX_TEAM_SIZE,
        "period": period.query_params() or {"all_time": True},
        "game_size": game_size,
        "observed_duo_teams": observed_duo_teams[:limit],
        "individual_rankings": [
            _ranking_row(row) for row in individual_rankings[:limit]
        ],
        "guidance": (
            "Recommend pairings from observed_duo_teams using rank_score, wins_display, "
            "and games_played. Use individual_rankings only as supporting context. "
            "Do not recommend pairs that never played together unless the tool returns "
            "no observed_duo_teams; say data is limited instead."
        ),
    }
    note = scoring_interpretation_note(game_type_code)
    if note:
        payload["scoring_note"] = note
    if game_filters is not None and game_filters.is_active():
        payload.update(
            game_features_response_payload(
                game_filters.as_selections(),
                game_type_code=game_type_code,
            )
        )
    return payload
