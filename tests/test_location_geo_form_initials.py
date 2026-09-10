"""Hidden geo field initials on Edit game."""

import re

import pytest
from django.contrib.auth.models import User
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from leaderlodge.games.forms import GameEditForm
from leaderlodge.games.models import Game, GameParticipantResult
from leaderlodge.groups.location_geo import GEOCODE_SOURCE_MAP_PIN, location_geo
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


@pytest.fixture
def pinned_location_game(staff_user, group):
    players = list(group.players.order_by("pk"))
    location = resolve_game_location(
        group=group,
        location_name="Kitchen",
        geo=location_geo(
            lat=34.0522,
            lon=-118.2437,
            geocode_source=GEOCODE_SOURCE_MAP_PIN,
        ),
    )
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
def test_game_edit_form_seeds_hidden_geo_from_location(pinned_location_game):
    form = GameEditForm(game=pinned_location_game)
    assert form.fields["location_lat"].initial == pytest.approx(34.0522)
    assert form.fields["location_lon"].initial == pytest.approx(-118.2437)
    assert form.fields["location_geocode_source"].initial == GEOCODE_SOURCE_MAP_PIN


@override_settings(GOOGLE_PLACES_API_KEY="test-browser-key")
@pytest.mark.django_db
def test_edit_game_shows_pin_badge_for_geocoded_location(
    client, staff_user, pinned_location_game
):
    client.force_login(staff_user)
    url = reverse("games:edit_game", kwargs={"pk": pinned_location_game.pk})
    content = client.get(url).content.decode()
    pin_status_start = content.index("data-location-pin-status")
    pin_status_end = content.index("data-location-set-place", pin_status_start)
    pin_status = content[pin_status_start:pin_status_end]
    badge_match = re.search(
        r'<span[^>]*data-location-pin-badge[^>]*>',
        pin_status,
    ) or re.search(r'<span[^>]*data-location-pin-badge', pin_status)
    assert badge_match is not None
    badge_tag = badge_match.group(0)
    assert "location-geocoded-badge" in badge_tag
    assert "d-none" not in badge_tag

    empty_match = re.search(
        r'<span[^>]*data-location-pin-empty[^>]*>',
        pin_status,
    )
    assert empty_match is not None
    assert "d-none" in empty_match.group(0)
