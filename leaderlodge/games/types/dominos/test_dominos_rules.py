import pytest
from django.core.exceptions import ValidationError

from leaderlodge.games.types.dominos import rules as dominos_rules


@pytest.mark.parametrize("player_count", [2, 3, 4])
def test_dominos_accepts_valid_player_counts(player_count):
    dominos_rules.validate_game(
        player_count=player_count,
        winner_count=1,
        tie_count=0,
        loser_count=0,
    )


def test_dominos_accepts_tie():
    dominos_rules.validate_game(
        player_count=2,
        winner_count=0,
        tie_count=2,
        loser_count=0,
    )


def test_dominos_rejects_loser():
    with pytest.raises(ValidationError):
        dominos_rules.validate_game(
            player_count=2,
            winner_count=1,
            tie_count=0,
            loser_count=1,
        )
