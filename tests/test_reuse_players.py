import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from datetime import date

from leaderlodge.games.reuse_players import (
    REUSE_PLAYERS_MAX_GAMES,
    most_recent_game,
    previous_game_participant_rows,
    reuse_players_summary,
)
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
            ParticipantInput(player=players[0], score=30, result="win", placement=0),
            ParticipantInput(player=players[1], score=20, result="played", placement=1),
        ],
    )
    record_game(
        user=user,
        group=group,
        game_type_code="dominos",
        played_on=date(2026, 2, 1),
        participants=[
            ParticipantInput(player=players[1], score=40, result="win", placement=0),
            ParticipantInput(player=players[0], score=10, result="played", placement=1),
        ],
    )

    rows = previous_game_participant_rows(group, "dominos")
    assert [row["display_label"] for row in rows] == [
        players[1].display_label,
        players[0].display_label,
    ]


@pytest.mark.django_db
def test_most_recent_game_is_scoped_by_group_and_game_type(user, group):
    players = list(group.players.order_by("pk")[:2])
    other_group = create_group_with_owner(user=user, name="Other Club")
    add_guest_player(group=other_group, display_name="Alex")

    record_game(
        user=user,
        group=group,
        game_type_code="dominos",
        played_on=date(2026, 1, 1),
        participants=[
            ParticipantInput(player=players[0], score=30, result="win", placement=0),
            ParticipantInput(player=players[1], score=20, result="played", placement=1),
        ],
    )
    record_game(
        user=user,
        group=group,
        game_type_code="backgammon",
        played_on=date(2026, 2, 1),
        participants=[
            ParticipantInput(player=players[1], score=1, result="win", placement=0),
            ParticipantInput(player=players[0], score=0, result="played", placement=1),
        ],
    )

    dominos_game = most_recent_game(group, "dominos")
    backgammon_game = most_recent_game(group, "backgammon")
    other_group_game = most_recent_game(other_group, "dominos")

    assert dominos_game is not None
    assert dominos_game.game_type_code == "dominos"
    assert backgammon_game is not None
    assert backgammon_game.game_type_code == "backgammon"
    assert other_group_game is None


@pytest.mark.django_db
def test_reuse_players_summary_lists_up_to_max_unique_lineups(user, group):
    from leaderlodge.groups.services import add_guest_player

    players = list(group.players.order_by("pk")[:2])
    extras = [
        add_guest_player(group=group, display_name=name)
        for name in ("Alex", "Blake", "Casey", "Drew", "Eden", "Finn")
    ]
    # Duplicate newest lineup first, then unique lineups further back.
    record_game(
        user=user,
        group=group,
        game_type_code="dominos",
        played_on=date(2026, 2, 10),
        participants=[
            ParticipantInput(player=players[0], score=30, result="win", placement=0),
            ParticipantInput(player=players[1], score=20, result="played", placement=1),
        ],
    )
    record_game(
        user=user,
        group=group,
        game_type_code="dominos",
        played_on=date(2026, 2, 9),
        participants=[
            ParticipantInput(player=players[0], score=25, result="win", placement=0),
            ParticipantInput(player=players[1], score=15, result="played", placement=1),
        ],
    )
    unique_games = []
    for index, partner in enumerate(extras):
        unique_games.append(
            record_game(
                user=user,
                group=group,
                game_type_code="dominos",
                played_on=date(2026, 1, 20 - index),
                participants=[
                    ParticipantInput(
                        player=players[0], score=30, result="win", placement=0
                    ),
                    ParticipantInput(
                        player=partner, score=20, result="played", placement=1
                    ),
                ],
            )
        )

    summary = reuse_players_summary(group, "dominos")
    assert len(summary["options"]) == REUSE_PLAYERS_MAX_GAMES
    # Newest unique lineup first (the duplicate pair), then distinct partners.
    assert summary["options"][0]["summary"] == (
        f"{players[0].display_label}, {players[1].display_label}"
    )
    assert [option["game_id"] for option in summary["options"][1:]] == [
        game.pk for game in unique_games[: REUSE_PLAYERS_MAX_GAMES - 1]
    ]


@pytest.mark.django_db
def test_reuse_players_summary_respects_scan_limit(user, group):
    from leaderlodge.groups.services import add_guest_player

    players = list(group.players.order_by("pk")[:2])
    alex = add_guest_player(group=group, display_name="Alex")
    # Many duplicate newest lineups, then one unique lineup older than the scan window.
    for day in range(1, 6):
        record_game(
            user=user,
            group=group,
            game_type_code="dominos",
            played_on=date(2026, 3, day),
            participants=[
                ParticipantInput(
                    player=players[0], score=30, result="win", placement=0
                ),
                ParticipantInput(
                    player=players[1], score=20, result="played", placement=1
                ),
            ],
        )
    older_unique = record_game(
        user=user,
        group=group,
        game_type_code="dominos",
        played_on=date(2026, 1, 1),
        participants=[
            ParticipantInput(player=players[0], score=30, result="win", placement=0),
            ParticipantInput(player=alex, score=20, result="played", placement=1),
        ],
    )

    summary = reuse_players_summary(group, "dominos", scan_limit=3)
    assert len(summary["options"]) == 1
    assert older_unique.pk not in [option["game_id"] for option in summary["options"]]


@pytest.mark.django_db
def test_game_reuse_preview_endpoint(client, user, group):
    from leaderlodge.groups.services import add_guest_player

    players = list(group.players.order_by("pk")[:2])
    other = add_guest_player(group=group, display_name="Alex")
    older = record_game(
        user=user,
        group=group,
        game_type_code="dominos",
        played_on=date(2026, 1, 1),
        participants=[
            ParticipantInput(player=players[0], score=30, result="win", placement=0),
            ParticipantInput(player=other, score=20, result="played", placement=1),
        ],
    )
    newer = record_game(
        user=user,
        group=group,
        game_type_code="dominos",
        played_on=date(2026, 2, 1),
        participants=[
            ParticipantInput(player=players[1], score=40, result="win", placement=0),
            ParticipantInput(player=players[0], score=10, result="played", placement=1),
        ],
    )
    # Same lineup as newer, different order/scores: should not appear twice.
    latest_same_lineup = record_game(
        user=user,
        group=group,
        game_type_code="dominos",
        played_on=date(2026, 3, 1),
        participants=[
            ParticipantInput(player=players[0], score=22, result="win", placement=0),
            ParticipantInput(player=players[1], score=11, result="played", placement=1),
        ],
    )

    client.force_login(user)
    response = client.get(
        reverse("games:reuse_preview"),
        {"group": str(group.pk), "game_type_code": "dominos"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["available"] is True
    assert [option["game_id"] for option in data["options"]] == [
        latest_same_lineup.pk,
        older.pk,
    ]
    assert data["options"][0]["summary"] == (
        f"{players[0].display_label}, {players[1].display_label}"
    )
    assert newer.pk not in [option["game_id"] for option in data["options"]]
