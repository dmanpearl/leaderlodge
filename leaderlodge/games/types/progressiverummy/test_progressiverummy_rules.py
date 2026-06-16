from leaderlodge.games.types.progressiverummy import rules as progressiverummy_rules


def test_progressiverummy_allows_multiple_losers():
    progressiverummy_rules.validate_game(
        player_count=3,
        winner_count=1,
        tie_count=0,
        loser_count=2,
    )


def test_progressiverummy_all_tie_no_loser():
    progressiverummy_rules.validate_game(
        player_count=3,
        winner_count=0,
        tie_count=3,
        loser_count=0,
    )
