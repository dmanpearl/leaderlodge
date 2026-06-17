from leaderlodge.games.registry import get_game_type
from leaderlodge.games.validators import validate_game_for_type


def test_progressiverummy_allows_multiple_losers():
    validate_game_for_type(
        game_type=get_game_type("progressiverummy"),
        player_count=3,
        winner_count=1,
        tie_count=0,
        loser_count=2,
    )


def test_progressiverummy_all_tie_no_loser():
    validate_game_for_type(
        game_type=get_game_type("progressiverummy"),
        player_count=3,
        winner_count=0,
        tie_count=3,
        loser_count=0,
    )
