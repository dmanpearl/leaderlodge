import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone

from datetime import date, timedelta

from leaderlodge.games.forms import GameRecordForm
from leaderlodge.games.last_location import (
    last_recorded_location_name,
    recent_location_names,
)
from leaderlodge.games.models import GameParticipantResult
from leaderlodge.games.services import ParticipantInput, record_game
from leaderlodge.groups.locations import resolve_game_location
from leaderlodge.groups.services import add_guest_player, create_group_with_owner

Result = GameParticipantResult.Result


@pytest.fixture
def staff_user(db):
    return User.objects.create_user(
        username="staff",
        password="test-pass-123",
        is_staff=True,
    )


@pytest.fixture
def group(staff_user):
    group = create_group_with_owner(user=staff_user, name="Dom Club")
    add_guest_player(group=group, display_name="Pat")
    add_guest_player(group=group, display_name="Sam")
    return group


@pytest.mark.django_db
def test_last_recorded_location_name_returns_latest_for_user_and_game_type(
    staff_user, group
):
    players = list(group.players.order_by("pk"))
    kitchen = resolve_game_location(group=group, location_name="Kitchen")
    clubhouse = resolve_game_location(group=group, location_name="Clubhouse")

    record_game(
        user=staff_user,
        group=group,
        game_type_code="dominos",
        played_on=timezone.localdate(),
        participants=[
            ParticipantInput(
                player=players[0], score=30, result=Result.WIN, placement=0
            ),
            ParticipantInput(
                player=players[1], score=20, result=Result.PLAYED, placement=1
            ),
        ],
        location=kitchen,
    )
    record_game(
        user=staff_user,
        group=group,
        game_type_code="dominos",
        played_on=timezone.localdate(),
        participants=[
            ParticipantInput(
                player=players[0], score=25, result=Result.WIN, placement=0
            ),
            ParticipantInput(
                player=players[1], score=15, result=Result.PLAYED, placement=1
            ),
        ],
        location=clubhouse,
    )
    record_game(
        user=staff_user,
        group=group,
        game_type_code="backgammon",
        played_on=timezone.localdate(),
        participants=[
            ParticipantInput(
                player=players[0], score=5, result=Result.WIN, placement=0
            ),
            ParticipantInput(
                player=players[1], score=0, result=Result.PLAYED, placement=1
            ),
        ],
        location=kitchen,
    )

    assert last_recorded_location_name(staff_user, "dominos") == "Clubhouse"
    assert last_recorded_location_name(staff_user, "backgammon") == "Kitchen"
    assert last_recorded_location_name(staff_user, "mahjongg") == ""


def _play(staff_user, group, players, *, game_type_code, location, played_on):
    return record_game(
        user=staff_user,
        group=group,
        game_type_code=game_type_code,
        played_on=played_on,
        participants=[
            ParticipantInput(
                player=players[0], score=30, result=Result.WIN, placement=0
            ),
            ParticipantInput(
                player=players[1], score=20, result=Result.PLAYED, placement=1
            ),
        ],
        location=location,
    )


@pytest.mark.django_db
def test_last_recorded_location_name_follows_latest_save_not_play_date(
    staff_user, group
):
    """A back-dated game saved just now is the next default location."""
    players = list(group.players.order_by("pk"))
    kitchen = resolve_game_location(group=group, location_name="Kitchen")
    clubhouse = resolve_game_location(group=group, location_name="Clubhouse")
    today = timezone.localdate()

    earlier_save = _play(
        staff_user,
        group,
        players,
        game_type_code="dominos",
        location=clubhouse,
        played_on=today,
    )
    earlier_save.created_at = timezone.now() - timedelta(days=3)
    earlier_save.save(update_fields=["created_at"])

    _play(
        staff_user,
        group,
        players,
        game_type_code="dominos",
        location=kitchen,
        played_on=today - timedelta(days=10),
    )

    assert last_recorded_location_name(staff_user, "dominos", group=group) == "Kitchen"


@pytest.mark.django_db
def test_last_recorded_location_name_stays_in_the_selected_group(staff_user, group):
    players = list(group.players.order_by("pk"))
    kitchen = resolve_game_location(group=group, location_name="Kitchen")
    other = create_group_with_owner(user=staff_user, name="Away Club")
    add_guest_player(group=other, display_name="Pat")
    add_guest_player(group=other, display_name="Sam")
    other_players = list(other.players.order_by("pk"))
    clubhouse = resolve_game_location(group=other, location_name="Clubhouse")
    today = timezone.localdate()

    home_game = _play(
        staff_user,
        group,
        players,
        game_type_code="dominos",
        location=kitchen,
        played_on=today,
    )
    home_game.created_at = timezone.now() - timedelta(hours=1)
    home_game.save(update_fields=["created_at"])
    _play(
        staff_user,
        other,
        other_players,
        game_type_code="dominos",
        location=clubhouse,
        played_on=today,
    )

    assert last_recorded_location_name(staff_user, "dominos", group=group) == "Kitchen"
    assert (
        last_recorded_location_name(staff_user, "dominos", group=other) == "Clubhouse"
    )

    form = GameRecordForm(
        user=staff_user,
        initial={"group": group.pk, "game_type_code": "dominos"},
    )
    assert form.initial["location_name"] == "Kitchen"


@pytest.mark.django_db
def test_game_reuse_preview_includes_last_location_name(client, staff_user, group):
    players = list(group.players.order_by("pk"))
    location = resolve_game_location(group=group, location_name="Kitchen")
    record_game(
        user=staff_user,
        group=group,
        game_type_code="dominos",
        played_on=timezone.localdate(),
        participants=[
            ParticipantInput(
                player=players[0], score=30, result=Result.WIN, placement=0
            ),
            ParticipantInput(
                player=players[1], score=20, result=Result.PLAYED, placement=1
            ),
        ],
        location=location,
    )

    client.force_login(staff_user)
    response = client.get(
        reverse("games:reuse_preview"),
        {"group": group.pk, "game_type_code": "dominos"},
    )

    assert response.status_code == 200
    assert response.json()["last_location_name"] == "Kitchen"


@pytest.mark.django_db
def test_recent_location_names_prefers_game_type_then_fills(staff_user, group):
    players = list(group.players.order_by("pk"))
    kitchen = resolve_game_location(group=group, location_name="Kitchen")
    patio = resolve_game_location(group=group, location_name="Patio")
    clubhouse = resolve_game_location(group=group, location_name="Clubhouse")
    today = timezone.localdate()

    def _play(*, game_type_code, location, played_on):
        record_game(
            user=staff_user,
            group=group,
            game_type_code=game_type_code,
            played_on=played_on,
            participants=[
                ParticipantInput(
                    player=players[0], score=30, result=Result.WIN, placement=0
                ),
                ParticipantInput(
                    player=players[1], score=20, result=Result.PLAYED, placement=1
                ),
            ],
            location=location,
        )

    _play(
        game_type_code="dominos", location=kitchen, played_on=today - timedelta(days=3)
    )
    _play(game_type_code="dominos", location=patio, played_on=today - timedelta(days=1))
    _play(
        game_type_code="backgammon",
        location=clubhouse,
        played_on=today,
    )

    assert recent_location_names(group, game_type_code="dominos") == [
        "Patio",
        "Kitchen",
        "Clubhouse",
    ]
    assert recent_location_names(group, game_type_code="backgammon")[:1] == [
        "Clubhouse"
    ]


@pytest.mark.django_db
def test_group_locations_api_includes_recent(client, staff_user, group):
    players = list(group.players.order_by("pk"))
    kitchen = resolve_game_location(group=group, location_name="Kitchen")
    record_game(
        user=staff_user,
        group=group,
        game_type_code="dominos",
        played_on=date(2026, 1, 1),
        participants=[
            ParticipantInput(
                player=players[0], score=30, result=Result.WIN, placement=0
            ),
            ParticipantInput(
                player=players[1], score=20, result=Result.PLAYED, placement=1
            ),
        ],
        location=kitchen,
    )

    client.force_login(staff_user)
    response = client.get(
        reverse("groups:locations", kwargs={"pk": group.pk}),
        {"game_type_code": "dominos"},
    )
    assert response.status_code == 200
    data = response.json()
    assert {"name": "Kitchen"} in data["locations"]
    assert data["recent"] == [{"name": "Kitchen"}]


@pytest.mark.django_db
def test_record_game_setup_shows_recent_locations_control(client, staff_user, group):
    client.force_login(staff_user)
    response = client.get(reverse("games:create"))
    content = response.content.decode()
    assert response.status_code == 200
    assert "data-location-recent" in content
    assert "Recent" in content
