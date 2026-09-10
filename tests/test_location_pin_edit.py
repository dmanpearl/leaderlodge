"""Tests for location pin changes during game edit."""

import pytest
from django.contrib.auth.models import User
from django.contrib.messages import get_messages
from django.urls import reverse
from django.utils import timezone

from leaderlodge.games.models import Game, GameParticipantResult, GameScoreChangeLog
from leaderlodge.games.snapshot_diff import format_snapshot_diff
from leaderlodge.groups.locations import resolve_game_location
from leaderlodge.groups.services import add_guest_player, create_group_with_owner

from tests.conftest import edit_game_participant_post

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


@pytest.fixture
def game_with_unpinned_location(staff_user, group):
    players = list(group.players.order_by("pk"))
    location = resolve_game_location(group=group, location_name="Kitchen")
    assert location.lat is None
    game = Game.objects.create(
        group=group,
        game_type_code="dominos",
        played_on=timezone.localdate(),
        recorded_by=staff_user,
        player_count=2,
        location=location,
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
    return game


@pytest.mark.django_db
def test_game_edit_location_pin_only(client, staff_user, game_with_unpinned_location):
    game = game_with_unpinned_location
    client.force_login(staff_user)
    url = reverse("games:edit_game", kwargs={"pk": game.pk})
    post = edit_game_participant_post(
        game,
        location_name="Kitchen",
        notes="Set map pin for this venue.",
        location_lat="34.0522",
        location_lon="-118.2437",
        location_geocode_source="map_pin",
    )
    response = client.post(url, post)

    game.refresh_from_db()
    assert game.location.lat == pytest.approx(34.0522)
    assert game.location.lon == pytest.approx(-118.2437)
    assert GameScoreChangeLog.objects.filter(game=game).count() == 1
    log = GameScoreChangeLog.objects.get(game=game)
    assert log.new_snapshot["location"]["lat"] == pytest.approx(34.0522)
    assert log.old_snapshot["location"]["lat"] is None
    assert (
        format_snapshot_diff(log.old_snapshot, log.new_snapshot)
        == "location pin: (none) to 34.0522, -118.2437"
    )
    assert response.status_code == 302
    msgs = [str(m) for m in get_messages(response.wsgi_request)]
    assert "Game updated." in msgs
    assert "No changes were made." not in msgs
