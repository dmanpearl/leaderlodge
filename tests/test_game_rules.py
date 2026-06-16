import pytest
from django.core.exceptions import ValidationError

from leaderlodge.games.backgammon import rules as backgammon_rules
from leaderlodge.games.dominos import rules as dominos_rules
from leaderlodge.games.progressiverummy import rules as progressiverummy_rules
from leaderlodge.leaderboards.service import PlayerRanking


def test_player_ranking_includes_game_type():
    """Each ranking row is scoped to one game type."""
    fields = {f.name for f in PlayerRanking.__dataclass_fields__.values()}
    assert "game_type_code" in fields
    assert "game_type_name" in fields
    assert "player" in fields
    assert "rank" in fields


@pytest.mark.parametrize(
    "player_count",
    [2, 3, 4],
)
def test_dominos_accepts_valid_player_counts(player_count):
    dominos_rules.validate_game(
        player_count=player_count,
        winner_count=1,
        loser_count=0,
    )


def test_dominos_rejects_loser():
    with pytest.raises(ValidationError):
        dominos_rules.validate_game(
            player_count=2,
            winner_count=1,
            loser_count=1,
        )


def test_progressiverummy_requires_loser():
    progressiverummy_rules.validate_game(
        player_count=4,
        winner_count=1,
        loser_count=1,
    )
    with pytest.raises(ValidationError):
        progressiverummy_rules.validate_game(
            player_count=4,
            winner_count=1,
            loser_count=0,
        )


def test_backgammon_requires_two_players():
    backgammon_rules.validate_game(
        player_count=2,
        winner_count=1,
        loser_count=0,
    )
    with pytest.raises(ValidationError):
        backgammon_rules.validate_game(
            player_count=3,
            winner_count=1,
            loser_count=0,
        )
