from leaderlodge.leaderboards.service import PlayerRanking


def test_player_ranking_includes_game_type():
    """Each ranking row is scoped to one game type."""
    fields = {f.name for f in PlayerRanking.__dataclass_fields__.values()}
    assert "game_type_code" in fields
    assert "game_type_name" in fields
    assert "player" in fields
    assert "rank" in fields
