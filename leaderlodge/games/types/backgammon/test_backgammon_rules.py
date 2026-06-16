import pytest
from django.core.exceptions import ValidationError

from leaderlodge.games.types.backgammon import rules as backgammon_rules


def test_backgammon_requires_two_players():
    backgammon_rules.validate_game(
        player_count=2,
        winner_count=1,
        tie_count=0,
        loser_count=0,
    )
    with pytest.raises(ValidationError):
        backgammon_rules.validate_game(
            player_count=3,
            winner_count=1,
            tie_count=0,
            loser_count=0,
        )
