from __future__ import annotations

COMFORTABLE_MAX_PLAYERS = 4
COMPACT_MAX_PLAYERS = 7


def resolve_game_list_density(*, table_player_count: int, stats_player_count: int) -> str:
    """
    Choose a layout density tier from the widest player column set on the page.

    Uses the max of table columns (current page) and stats columns (full filter)
    so both blocks stay readable together.
    """
    player_count = max(table_player_count, stats_player_count, 0)
    if player_count >= COMPACT_MAX_PLAYERS + 1:
        return "dense"
    if player_count >= COMFORTABLE_MAX_PLAYERS + 1:
        return "compact"
    return "comfortable"


def game_list_date_format(density: str) -> str:
    return "n/j/y"
