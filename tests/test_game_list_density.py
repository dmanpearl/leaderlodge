import pytest

from leaderlodge.games.list_density import resolve_game_list_density


@pytest.mark.parametrize(
    ("table_players", "stats_players", "expected"),
    [
        (2, 2, "comfortable"),
        (4, 3, "comfortable"),
        (5, 5, "compact"),
        (7, 4, "compact"),
        (8, 2, "dense"),
        (2, 9, "dense"),
        (0, 0, "comfortable"),
    ],
)
def test_resolve_game_list_density(table_players, stats_players, expected):
    assert (
        resolve_game_list_density(
            table_player_count=table_players,
            stats_player_count=stats_players,
        )
        == expected
    )
