import pytest
from django.core.exceptions import ValidationError

from leaderlodge.games.registry import get_game_type
from leaderlodge.games.validators import validate_game_for_type


@pytest.mark.parametrize("player_count", [2, 3, 4])
def test_dominos_accepts_valid_player_counts(player_count):
    validate_game_for_type(
        game_type=get_game_type("dominos"),
        player_count=player_count,
        winner_count=1,
        tie_count=0,
        loser_count=0,
    )


def test_dominos_rejects_five_players():
    with pytest.raises(ValidationError):
        validate_game_for_type(
            game_type=get_game_type("dominos"),
            player_count=5,
            winner_count=1,
            tie_count=0,
            loser_count=0,
        )


def test_dominos_accepts_tie():
    validate_game_for_type(
        game_type=get_game_type("dominos"),
        player_count=2,
        winner_count=0,
        tie_count=2,
        loser_count=0,
    )


def test_dominos_rejects_loser():
    with pytest.raises(ValidationError):
        validate_game_for_type(
            game_type=get_game_type("dominos"),
            player_count=2,
            winner_count=1,
            tie_count=0,
            loser_count=1,
        )
