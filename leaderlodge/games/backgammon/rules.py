from leaderlodge.games.common.validators import (
    validate_game_results,
    validate_player_count,
)


def validate_game(
    *,
    player_count: int,
    winner_count: int,
    tie_count: int,
    loser_count: int,
) -> None:
    validate_player_count(
        player_count=player_count,
        min_players=2,
        max_players=2,
    )
    validate_game_results(
        supports_loser=False,
        player_count=player_count,
        winner_count=winner_count,
        tie_count=tie_count,
        loser_count=loser_count,
    )
