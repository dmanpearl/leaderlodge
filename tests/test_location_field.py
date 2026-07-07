import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone

from leaderlodge.games.last_location import last_recorded_location_name
from leaderlodge.games.models import Game, GameParticipantResult
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


@pytest.mark.django_db
def test_game_create_prepopulates_last_location(client, staff_user, group):
    players = list(group.players.order_by("pk"))
    location = resolve_game_location(group=group, location_name="Sally")
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
        reverse("games:create"),
        {"game_type_code": "dominos", "group": group.pk},
    )
    content = response.content.decode()

    assert response.status_code == 200
    assert 'name="location_name"' in content
    assert 'value="Sally"' in content
    assert "data-location-clear" in content


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
def test_location_field_disables_native_suggestions(client, staff_user, group):
    client.force_login(staff_user)
    response = client.get(
        reverse("games:create"),
        {"game_type_code": "dominos", "group": group.pk},
    )
    content = response.content.decode()

    assert response.status_code == 200
    assert 'autocorrect="off"' in content
    assert 'autocapitalize="off"' in content
    assert 'spellcheck="false"' in content


@pytest.mark.django_db
def test_game_edit_includes_location_clear_button(client, staff_user, group):
    players = list(group.players.order_by("pk"))
    game = Game.objects.create(
        group=group,
        game_type_code="dominos",
        played_on=timezone.localdate(),
        recorded_by=staff_user,
        player_count=2,
        location=resolve_game_location(group=group, location_name="Sally"),
    )
    GameParticipantResult.objects.create(
        game=game,
        player=players[0],
        score=30,
        result=Result.WIN,
        placement=0,
    )
    GameParticipantResult.objects.create(
        game=game,
        player=players[1],
        score=20,
        result=Result.PLAYED,
        placement=1,
    )

    client.force_login(staff_user)
    response = client.get(reverse("games:edit_game", kwargs={"pk": game.pk}))
    content = response.content.decode()

    assert response.status_code == 200
    assert "data-location-clear" in content
    assert 'value="Sally"' in content
