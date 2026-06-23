import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from datetime import date

from leaderlodge.games.reuse_players import previous_game_participant_rows, reuse_players_summary
from leaderlodge.games.services import ParticipantInput, record_game
from leaderlodge.groups.services import add_guest_player, create_group_with_owner


@pytest.fixture
def user(db):
    return User.objects.create_user(username="david", password="test-pass-123")


@pytest.fixture
def group(user):
    group = create_group_with_owner(user=user, name="Dom Club")
    add_guest_player(group=group, display_name="Pat")
    return group


@pytest.mark.django_db
def test_previous_game_participant_rows_returns_latest_game(user, group):
    players = list(group.players.order_by("pk")[:2])
    record_game(
        user=user,
        group=group,
        game_type_code="dominos",
        played_on=date(2026, 1, 1),
        participants=[
            ParticipantInput(
                player=players[0], score=30, result="win", placement=0
            ),
            ParticipantInput(
                player=players[1], score=20, result="played", placement=1
            ),
        ],
    )
    record_game(
        user=user,
        group=group,
        game_type_code="dominos",
        played_on=date(2026, 2, 1),
        participants=[
            ParticipantInput(
                player=players[1], score=40, result="win", placement=0
            ),
            ParticipantInput(
                player=players[0], score=10, result="played", placement=1
            ),
        ],
    )

    rows = previous_game_participant_rows(group, "dominos")
    assert [row["display_label"] for row in rows] == [
        players[1].display_label,
        players[0].display_label,
    ]


@pytest.mark.django_db
def test_previous_game_participant_rows_is_scoped_by_group_and_game_type(user, group):
    players = list(group.players.order_by("pk")[:2])
    other_group = create_group_with_owner(user=user, name="Other Club")
    add_guest_player(group=other_group, display_name="Alex")

    record_game(
        user=user,
        group=group,
        game_type_code="dominos",
        played_on=date(2026, 1, 1),
        participants=[
            ParticipantInput(
                player=players[0], score=30, result="win", placement=0
            ),
            ParticipantInput(
                player=players[1], score=20, result="played", placement=1
            ),
        ],
    )
    record_game(
        user=user,
        group=group,
        game_type_code="backgammon",
        played_on=date(2026, 2, 1),
        participants=[
            ParticipantInput(
                player=players[1], score=1, result="win", placement=0
            ),
            ParticipantInput(
                player=players[0], score=0, result="played", placement=1
            ),
        ],
    )

    dominos_rows = previous_game_participant_rows(group, "dominos")
    backgammon_rows = previous_game_participant_rows(group, "backgammon")
    other_group_rows = previous_game_participant_rows(other_group, "dominos")

    assert len(dominos_rows) == 2
    assert len(backgammon_rows) == 2
    assert other_group_rows == []


@pytest.mark.django_db
def test_reuse_players_summary(user, group):
    players = list(group.players.order_by("pk")[:2])
    record_game(
        user=user,
        group=group,
        game_type_code="dominos",
        played_on=date(2026, 1, 1),
        participants=[
            ParticipantInput(
                player=players[0], score=30, result="win", placement=0
            ),
            ParticipantInput(
                player=players[1], score=20, result="played", placement=1
            ),
        ],
    )

    summary = reuse_players_summary(group, "dominos")
    assert summary["available"] is True
    assert summary["summary"] == f"{players[0].display_label}, {players[1].display_label}"


@pytest.mark.django_db
def test_game_reuse_preview_endpoint(client, user, group):
    players = list(group.players.order_by("pk")[:2])
    record_game(
        user=user,
        group=group,
        game_type_code="dominos",
        played_on=date(2026, 1, 1),
        participants=[
            ParticipantInput(
                player=players[0], score=30, result="win", placement=0
            ),
            ParticipantInput(
                player=players[1], score=20, result="played", placement=1
            ),
        ],
    )

    client.force_login(user)
    response = client.get(
        reverse("games:reuse_preview"),
        {"group": str(group.pk), "game_type": "dominos"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["available"] is True
    assert players[0].display_label in data["summary"]
