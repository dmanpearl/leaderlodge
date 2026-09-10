"""Map picker visibility on Edit game."""

import pytest
from django.contrib.auth.models import User
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from leaderlodge.games.models import Game, GameParticipantResult
from leaderlodge.groups.locations import resolve_game_location
from leaderlodge.groups.services import (
    add_group_member,
    add_guest_player,
    create_group_with_owner,
)

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
def member_user(db, group):
    user = User.objects.create_user(username="member", password="test-pass-123")
    add_group_member(group=group, user=user)
    return user


@pytest.fixture
def unpinned_location_game(staff_user, group):
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


@pytest.fixture
def member_unpinned_location_game(member_user, group):
    players = list(group.players.order_by("pk"))
    location = resolve_game_location(group=group, location_name="Patio")
    game = Game.objects.create(
        group=group,
        game_type_code="dominos",
        played_on=timezone.localdate(),
        recorded_by=member_user,
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


@override_settings(GOOGLE_PLACES_API_KEY="test-browser-key")
@pytest.mark.django_db
def test_group_owner_sees_assign_map_on_edit_game(
    client, staff_user, unpinned_location_game
):
    client.force_login(staff_user)
    url = reverse("games:edit_game", kwargs={"pk": unpinned_location_game.pk})
    content = client.get(url).content.decode()
    assert "data-location-set-place" in content
    assert "data-location-pin-status" in content
    assert "No pin yet for this location" in content
    assert "location-geocoded-badge d-none" in content


@override_settings(GOOGLE_PLACES_API_KEY="test-browser-key")
@pytest.mark.django_db
def test_member_sees_record_map_on_edit_game(
    client, member_user, member_unpinned_location_game
):
    client.force_login(member_user)
    url = reverse("games:edit_game", kwargs={"pk": member_unpinned_location_game.pk})
    content = client.get(url).content.decode()
    assert "data-location-record-place" in content
    assert "data-location-set-place" not in content
    assert "data-location-pin-status" in content


@override_settings(GOOGLE_PLACES_API_KEY="test-browser-key")
@pytest.mark.django_db
def test_edit_game_includes_location_geo_hidden_fields(
    client, staff_user, unpinned_location_game
):
    client.force_login(staff_user)
    url = reverse("games:edit_game", kwargs={"pk": unpinned_location_game.pk})
    content = client.get(url).content.decode()
    assert 'data-location-geo="lat"' in content
    assert 'data-location-geo="lon"' in content
