from datetime import date

import pytest
from django.test import override_settings
from django.urls import reverse

from leaderlodge.games.scoring import assign_results_from_scores
from leaderlodge.games.services import ParticipantInput, record_game
from leaderlodge.groups.services import add_guest_player, create_group_with_owner
from leaderlodge.leaderboards.period import (
    PERIOD_PRESET_LAST_7_DAYS,
    PERIOD_PRESET_LAST_WEEK,
    PERIOD_PRESET_LAST_WEEKEND,
    PERIOD_PRESET_TODAY,
    PERIOD_PRESET_YESTERDAY,
    LeaderboardPeriod,
    available_leaderboard_periods,
    dates_for_period_preset,
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


def test_dates_for_period_presets_use_today():
    today = date(2026, 7, 15)  # Wednesday
    assert dates_for_period_preset(PERIOD_PRESET_TODAY, today=today) == (
        today,
        today,
    )
    assert dates_for_period_preset(PERIOD_PRESET_YESTERDAY, today=today) == (
        date(2026, 7, 14),
        date(2026, 7, 14),
    )
    assert dates_for_period_preset(PERIOD_PRESET_LAST_7_DAYS, today=today) == (
        date(2026, 7, 9),
        today,
    )
    assert dates_for_period_preset(PERIOD_PRESET_LAST_WEEKEND, today=today) == (
        date(2026, 7, 11),
        date(2026, 7, 12),
    )
    assert dates_for_period_preset(PERIOD_PRESET_LAST_WEEK, today=today) == (
        date(2026, 7, 6),
        date(2026, 7, 12),
    )


def test_resolve_leaderboard_period_prefers_preset_over_year():
    period = resolve_leaderboard_period(
        raw_year="2026",
        raw_month="6",
        raw_preset=PERIOD_PRESET_YESTERDAY,
        available_years=[2026],
        months_by_year={2026: (6, 5)},
        today=date(2026, 7, 15),
    )
    assert period.preset == PERIOD_PRESET_YESTERDAY
    assert period.start_date == date(2026, 7, 14)
    assert period.end_date == date(2026, 7, 14)
    assert period.year is None


def test_resolve_leaderboard_period_custom_date_range():
    period = resolve_leaderboard_period(
        raw_start_date="2026-07-01",
        raw_end_date="2026-07-03",
        available_years=[2026],
        months_by_year={2026: (7,)},
    )
    assert period.has_date_range
    assert period.display_label() == "Jul 1, 2026 to Jul 3, 2026"
    assert period.query_params() == {
        "start_date": "2026-07-01",
        "end_date": "2026-07-03",
    }


@pytest.mark.django_db
def test_get_player_rankings_filters_by_date_range(user, group):
    _record_dominos_game(group, user, played_on=date(2026, 7, 1))
    _record_dominos_game(
        group, user, played_on=date(2026, 7, 10), winner_idx=1, loser_idx=0
    )

    july_first = get_player_rankings(
        group,
        game_type_code="dominos",
        period=LeaderboardPeriod(
            start_date=date(2026, 7, 1),
            end_date=date(2026, 7, 1),
        ),
    )
    assert len(july_first) == 2
    assert july_first[0].games_played == 1
    assert july_first[0].wins == 1


@pytest.mark.django_db
def test_leaderboard_index_shows_quick_range_filter(client, user, group):
    client.force_login(user)
    _record_dominos_game(group, user, played_on=date(2026, 3, 1))

    response = client.get(
        reverse("leaderboards:index"),
        {
            "group": str(group.pk),
            "game_type_code": "dominos",
            "period_preset": "yesterday",
        },
    )
    content = response.content.decode()
    assert response.status_code == 200
    assert 'name="period_preset"' in content
    assert "Yesterday" in content
    assert "Quick range" in content


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
def test_leaderboard_index_shows_disabled_game_types_without_games(client, user, group):
    client.force_login(user)
    _record_dominos_game(group, user, played_on=date(2026, 3, 1))

    response = client.get(
        reverse("leaderboards:index"),
        {"group": str(group.pk), "game_type_code": "dominos"},
    )
    content = response.content.decode()
    assert response.status_code == 200
    assert 'value="dominos"' in content
    assert 'value="pickleball"' in content
    assert 'value="pickleball" disabled' in content or (
        'value="pickleball"' in content and "disabled" in content
    )
    assert "Pickleball" in content


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
