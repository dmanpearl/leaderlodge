import pytest
from datetime import date

from django.contrib.auth.models import User
from django.urls import reverse

from leaderlodge.games.scoring import assign_results_from_scores
from leaderlodge.games.services import ParticipantInput, record_game
from leaderlodge.groups.services import add_guest_player, create_group_with_owner
from leaderlodge.leaderboards.hall_of_fame import (
    GRANULARITY_MONTH,
    build_hall_of_fame_grid,
)


@pytest.fixture
def user(db):
    return User.objects.create_user(username="david", password="test-pass-123")


@pytest.fixture
def group(user):
    group = create_group_with_owner(user=user, name="Dom Club")
    add_guest_player(group=group, display_name="Pat")
    return group


def _record_dated_game(user, group, *, played_on, winner_score=30, loser_score=20):
    players = list(group.players.order_by("pk")[:2])
    rows = [
        {"player": players[0], "score": winner_score},
        {"player": players[1], "score": loser_score},
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
    return players[0]


@pytest.mark.django_db
def test_hall_of_fame_year_grid_shows_leaders(client, user, group):
    client.force_login(user)
    winner_2024 = _record_dated_game(user, group, played_on=date(2024, 6, 15))
    _record_dated_game(
        user,
        group,
        played_on=date(2025, 3, 10),
        winner_score=40,
        loser_score=10,
    )

    content = client.get(
        reverse("leaderboards:hall_of_fame"),
        {"group": str(group.pk)},
        follow=True,
    ).content.decode()

    assert "hall-of-fame-table" in content
    assert ">2025</th>" in content
    assert ">2024</th>" in content
    assert ">Dominos</th>" in content
    assert winner_2024.display_label in content


@pytest.mark.django_db
def test_hall_of_fame_month_grid_labels(client, user, group):
    client.force_login(user)
    _record_dated_game(user, group, played_on=date(2026, 1, 5))

    content = client.get(
        reverse("leaderboards:hall_of_fame"),
        {"group": str(group.pk), "granularity": GRANULARITY_MONTH},
        follow=True,
    ).content.decode()

    assert ">Month</th>" in content
    assert ">Jan, 2026</th>" in content


@pytest.mark.django_db
def test_build_hall_of_fame_grid_orders_newest_first(user, group):
    _record_dated_game(user, group, played_on=date(2024, 1, 1))
    _record_dated_game(user, group, played_on=date(2026, 2, 1))

    grid = build_hall_of_fame_grid(group, granularity="year")
    assert [row.label for row in grid.rows] == ["2026", "2024"]

    month_grid = build_hall_of_fame_grid(group, granularity=GRANULARITY_MONTH)
    assert month_grid.rows[0].label == "Feb, 2026"


@pytest.mark.django_db
def test_hall_of_fame_cell_links_to_rank_detail(client, user, group):
    client.force_login(user)
    winner = _record_dated_game(user, group, played_on=date(2025, 7, 4))

    content = client.get(
        reverse("leaderboards:hall_of_fame"),
        {"group": str(group.pk), "granularity": GRANULARITY_MONTH},
        follow=True,
    ).content.decode()

    assert (
        f'href="/leaderboards/detail/?group={group.pk}&amp;game_type_code=dominos&amp;year=2025&amp;month=7&amp;player={winner.pk}"'
        in content
    )
