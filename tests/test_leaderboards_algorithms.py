from datetime import date

import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from leaderlodge.games.scoring import assign_results_from_scores
from leaderlodge.games.services import ParticipantInput, record_game
from leaderlodge.groups.services import add_guest_player, create_group_with_owner
from leaderlodge.leaderboards.algorithms import (
    ALGORITHM_BAYESIAN,
    ALGORITHM_WIN_PERCENT,
    ALGORITHM_WIN_TOTAL,
    resolve_rank_algorithm,
)
from leaderlodge.leaderboards.period import (
    LeaderboardPeriod,
    build_leaderboard_query,
)
from leaderlodge.leaderboards.service import get_player_rankings


@pytest.fixture
def user(db):
    return User.objects.create_user(username="david", password="test-pass-123")


@pytest.fixture
def group(user):
    group = create_group_with_owner(user=user, name="Dom Club")
    add_guest_player(group=group, display_name="Pat")
    add_guest_player(group=group, display_name="Sam")
    return group


def _record(user, group, *, winner_idx, loser_idx, played_on, winner_score=35):
    players = list(group.players.order_by("pk"))
    rows = [
        {"player": players[winner_idx], "score": winner_score},
        {"player": players[loser_idx], "score": 10},
    ]
    assign_results_from_scores(rows, "dominos")
    return record_game(
        user=user,
        group=group,
        game_type_code="dominos",
        played_on=played_on,
        participants=[
            ParticipantInput(
                player=row["player"],
                score=row["score"],
                result=row["result"],
                placement=row["placement"],
            )
            for row in rows
        ],
    )


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("", ALGORITHM_BAYESIAN),
        (None, ALGORITHM_BAYESIAN),
        ("bayesian", ALGORITHM_BAYESIAN),
        ("win_percent", ALGORITHM_WIN_PERCENT),
        ("win_total", ALGORITHM_WIN_TOTAL),
        ("nope", ALGORITHM_BAYESIAN),
        ("WIN_PERCENT", ALGORITHM_WIN_PERCENT),
    ],
)
def test_resolve_rank_algorithm(raw, expected):
    assert resolve_rank_algorithm(raw) == expected


def test_build_leaderboard_query_omits_bayesian_algorithm():
    query = build_leaderboard_query(
        group_id="1",
        game_type_code="dominos",
        algorithm=ALGORITHM_BAYESIAN,
    )
    assert "algorithm=" not in query

    query_empty = build_leaderboard_query(
        group_id="1",
        game_type_code="dominos",
        algorithm="",
    )
    assert "algorithm=" not in query_empty

    query_pct = build_leaderboard_query(
        group_id="1",
        game_type_code="dominos",
        algorithm=ALGORITHM_WIN_PERCENT,
    )
    assert "algorithm=win_percent" in query_pct


@pytest.mark.django_db
def test_win_algorithms_reorder_relative_to_bayesian(user, group):
    players = list(group.players.order_by("pk"))
    # Player 0: one high-score win, then a loss (50% win rate, 1 win).
    _record(
        user,
        group,
        winner_idx=0,
        loser_idx=2,
        played_on=date(2026, 1, 1),
        winner_score=55,
    )
    _record(
        user,
        group,
        winner_idx=2,
        loser_idx=0,
        played_on=date(2026, 1, 2),
        winner_score=30,
    )
    # Player 1: three wins, no losses (100%, 3 wins).
    for day in (3, 4, 5):
        _record(
            user,
            group,
            winner_idx=1,
            loser_idx=2,
            played_on=date(2026, 1, day),
            winner_score=30,
        )

    by_wins = get_player_rankings(
        group,
        game_type_code="dominos",
        algorithm=ALGORITHM_WIN_TOTAL,
    )
    by_pct = get_player_rankings(
        group,
        game_type_code="dominos",
        algorithm=ALGORITHM_WIN_PERCENT,
    )

    assert by_wins[0].player.pk == players[1].pk
    assert by_pct[0].player.pk == players[1].pk
    assert by_wins[0].wins == pytest.approx(3.0)
    assert by_pct[0].win_pct == pytest.approx(100.0)


@pytest.mark.django_db
def test_win_percent_respects_period_filter(user, group):
    players = list(group.players.order_by("pk"))
    _record(
        user,
        group,
        winner_idx=0,
        loser_idx=1,
        played_on=date(2025, 6, 1),
        winner_score=40,
    )
    _record(
        user,
        group,
        winner_idx=1,
        loser_idx=0,
        played_on=date(2026, 3, 1),
        winner_score=40,
    )
    _record(
        user,
        group,
        winner_idx=1,
        loser_idx=2,
        played_on=date(2026, 3, 2),
        winner_score=40,
    )

    period = LeaderboardPeriod(year=2026)
    rankings = get_player_rankings(
        group,
        game_type_code="dominos",
        period=period,
        algorithm=ALGORITHM_WIN_PERCENT,
    )
    leader = rankings[0]
    assert leader.player.pk == players[1].pk
    assert leader.wins == pytest.approx(2.0)
    assert leader.games_played == pytest.approx(2.0)


@pytest.mark.django_db
def test_leaderboard_page_algorithm_select_and_order(client, user, group):
    players = list(group.players.order_by("pk"))
    _record(
        user,
        group,
        winner_idx=0,
        loser_idx=2,
        played_on=date(2026, 1, 1),
        winner_score=55,
    )
    for day in (2, 3, 4):
        _record(
            user,
            group,
            winner_idx=1,
            loser_idx=2,
            played_on=date(2026, 1, day),
            winner_score=30,
        )

    client.force_login(user)
    response = client.get(
        reverse("leaderboards:index"),
        {
            "group": str(group.pk),
            "type": "dominos",
            "algorithm": "win_total",
        },
    )
    content = response.content.decode()
    assert response.status_code == 200
    assert 'id="leaderboard-algorithm"' in content
    assert "Rank Algorithm" in content
    assert "Bayesian (default)" in content
    assert "Win Percent" in content
    assert "Wins Total" in content
    assert ">Wins</th>" in content
    # First ranked player cell should be Pat (guest with three wins).
    table = content.split("leaderboard-table", 1)[1]
    first_row = table.split("<tr", 2)[2]
    assert players[1].display_label in first_row
