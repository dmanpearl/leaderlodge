from datetime import date

import pytest
from django.test import override_settings
from django.urls import reverse

from leaderlodge.games.scoring import assign_results_from_scores
from leaderlodge.games.services import ParticipantInput, record_game
from leaderlodge.groups.services import add_guest_player, create_group_with_owner
from leaderlodge.leaderboards.period import (
    LeaderboardPeriod,
    available_leaderboard_periods,
    resolve_leaderboard_period,
)
from leaderlodge.leaderboards.service import get_player_rankings


@pytest.fixture
def user(db):
    from django.contrib.auth.models import User

    return User.objects.create_user(username="david", password="test-pass-123")


@pytest.fixture
def group(user):
    group = create_group_with_owner(user=user, name="Dom Club")
    add_guest_player(group=group, display_name="Pat")
    add_guest_player(group=group, display_name="Sam")
    return group


def _record_dominos_game(group, user, *, played_on, winner_idx=0, loser_idx=1):
    players = list(group.players.order_by("pk"))
    rows = [
        {"player": players[winner_idx], "score": 35},
        {"player": players[loser_idx], "score": 20},
    ]
    assign_results_from_scores(rows, "dominos")
    participants = [
        ParticipantInput(
            player=row["player"],
            score=row["score"],
            result=row["result"],
            placement=row["placement"],
        )
        for row in rows
    ]
    record_game(
        user=user,
        group=group,
        game_type_code="dominos",
        played_on=played_on,
        participants=participants,
    )


def _record_three_player_dominos_game(group, user, *, played_on):
    players = list(group.players.order_by("pk")[:3])
    rows = [
        {"player": players[0], "score": 35},
        {"player": players[1], "score": 25},
        {"player": players[2], "score": 15},
    ]
    assign_results_from_scores(rows, "dominos")
    participants = [
        ParticipantInput(
            player=row["player"],
            score=row["score"],
            result=row["result"],
            placement=row["placement"],
        )
        for row in rows
    ]
    record_game(
        user=user,
        group=group,
        game_type_code="dominos",
        played_on=played_on,
        participants=participants,
    )


@pytest.mark.django_db
def test_resolve_leaderboard_period_ignores_month_without_year():
    period = resolve_leaderboard_period(
        raw_year="",
        raw_month="6",
        available_years=[2026],
        months_by_year={2026: (6, 5)},
    )
    assert period == LeaderboardPeriod.all_time()


@pytest.mark.django_db
def test_available_leaderboard_periods(user, group):
    _record_dominos_game(group, user, played_on=date(2026, 1, 15))
    _record_dominos_game(group, user, played_on=date(2026, 6, 10))
    _record_dominos_game(group, user, played_on=date(2025, 12, 1))

    years, months_by_year = available_leaderboard_periods(group, "dominos")
    assert years == [2026, 2025]
    assert months_by_year[2026] == (6, 1)
    assert months_by_year[2025] == (12,)


@pytest.mark.django_db
def test_get_player_rankings_filters_by_year(user, group):
    _record_dominos_game(group, user, played_on=date(2026, 1, 15))
    _record_dominos_game(
        group, user, played_on=date(2025, 12, 1), winner_idx=1, loser_idx=0
    )

    all_time = get_player_rankings(group, game_type_code="dominos")
    year_2026 = get_player_rankings(
        group,
        game_type_code="dominos",
        period=LeaderboardPeriod(year=2026),
    )

    assert len(all_time) == 2
    assert len(year_2026) == 2
    leader_2026 = year_2026[0]
    assert leader_2026.games_played == 1
    assert leader_2026.wins == 1


@pytest.mark.django_db
@override_settings(LEADERBOARD_VESTING_COUNT=20, LEADERBOARD_VESTING_FACTOR=0.5)
def test_period_filter_disables_vesting(user, group):
    _record_dominos_game(group, user, played_on=date(2026, 6, 1))

    all_time = get_player_rankings(
        group,
        game_type_code="dominos",
        period=LeaderboardPeriod.all_time(),
    )
    june = get_player_rankings(
        group,
        game_type_code="dominos",
        period=LeaderboardPeriod(year=2026, month=6),
    )

    winner_all_time = next(row for row in all_time if row.wins > 0)
    winner_june = next(row for row in june if row.wins > 0)
    assert winner_all_time.rank_score < winner_june.rank_score


@pytest.mark.django_db
def test_get_player_rankings_filters_by_game_size(user, group):
    add_guest_player(group=group, display_name="Alex")
    _record_dominos_game(group, user, played_on=date(2026, 1, 15))
    _record_three_player_dominos_game(group, user, played_on=date(2026, 1, 16))

    all_sizes = get_player_rankings(group, game_type_code="dominos")
    two_player = get_player_rankings(group, game_type_code="dominos", game_size=2)
    three_player = get_player_rankings(group, game_type_code="dominos", game_size=3)

    assert len(all_sizes) == 3
    assert all(row.games_played == 1 for row in two_player)
    assert len(two_player) == 2
    assert all(row.games_played == 1 for row in three_player)
    assert len(three_player) == 3


@pytest.mark.django_db
def test_leaderboard_index_shows_year_filter(client, user, group):
    client.force_login(user)
    _record_dominos_game(group, user, played_on=date(2026, 3, 1))

    response = client.get(
        reverse("leaderboards:index"),
        {"group": str(group.pk), "game_type_code": "dominos", "year": "2026"},
    )
    content = response.content.decode()
    assert response.status_code == 200
    assert 'id="leaderboard-year"' in content
    assert 'id="leaderboard-game-type-icon"' in content
    assert "game-types/dominos.png" in content
    assert "All years" in content
    assert "2026" in content
    assert "Dominos" in content and "2026" in content.split("card-header", 1)[1]


@pytest.mark.django_db
def test_leaderboard_index_shows_game_size_filter(client, user, group):
    add_guest_player(group=group, display_name="Alex")
    client.force_login(user)
    _record_dominos_game(group, user, played_on=date(2026, 3, 1))
    _record_three_player_dominos_game(group, user, played_on=date(2026, 3, 2))

    response = client.get(
        reverse("leaderboards:index"),
        {"group": str(group.pk), "game_type_code": "dominos", "game_size": "3"},
    )
    content = response.content.decode()
    assert response.status_code == 200
    assert 'id="leaderboard-game-size"' in content
    assert "All sizes" in content
    assert "3-player" in content


@pytest.mark.django_db
def test_rank_detail_preserves_period_in_back_link(client, user, group):
    client.force_login(user)
    _record_dominos_game(group, user, played_on=date(2026, 6, 1))
    player = group.players.order_by("pk").first()

    response = client.get(
        reverse("leaderboards:detail"),
        {
            "group": str(group.pk),
            "game_type_code": "dominos",
            "player": str(player.pk),
            "year": "2026",
            "month": "6",
        },
    )
    content = response.content.decode()
    assert response.status_code == 200
    assert "year=2026" in content
    assert "month=6" in content
    assert "June 2026" in content
