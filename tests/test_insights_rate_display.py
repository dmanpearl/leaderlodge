from leaderlodge.insights.tools.rate_display import (
    format_count_with_pct,
    format_pct_with_count_of_total,
    format_total_with_avg_per_game,
    format_avg_per_game_with_total,
)


def test_format_count_with_pct():
    assert format_count_with_pct(81, 25.1) == "81 (25.1%)"


def test_format_pct_with_count_of_total():
    assert format_pct_with_count_of_total(81, 25.1, 323) == "25.1% (81 of 323)"


def test_format_total_with_avg_per_game():
    assert format_total_with_avg_per_game(40440, 100) == "40,440 (404.4/game)"


def test_format_avg_per_game_with_total():
    assert format_avg_per_game_with_total(40440, 100) == "404.4/game (40,440 total)"
