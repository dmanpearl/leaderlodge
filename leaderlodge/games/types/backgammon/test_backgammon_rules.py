import pytest
from django.core.exceptions import ValidationError

from leaderlodge.games.registry import get_game_type
from leaderlodge.games.validators import validate_game_for_type


def test_backgammon_requires_two_players():
    game_type = get_game_type("backgammon")
    validate_game_for_type(
        game_type=game_type,
        player_count=2,
        winner_count=1,
        tie_count=0,
        loser_count=0,
    )
    with pytest.raises(ValidationError):
        validate_game_for_type(
            game_type=game_type,
            player_count=3,
            winner_count=1,
            tie_count=0,
            loser_count=0,
        )
