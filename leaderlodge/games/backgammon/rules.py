from leaderlodge.games.common.validators import (
    validate_player_count,
    validate_winner_loser,
)


def validate_game(*, player_count: int, winner_count: int, loser_count: int) -> None:
    validate_player_count(
        player_count=player_count,
        min_players=2,
        max_players=2,
    )
    validate_winner_loser(
        supports_loser=False,
        winner_count=winner_count,
        loser_count=loser_count,
    )
