from datetime import date

import pytest
from django.core.management import call_command
from django.contrib.auth.models import User

from leaderlodge.games.models import Game, GameParticipantResult
from leaderlodge.games.services import ParticipantInput, record_game
from leaderlodge.groups.location_geo import GEOCODE_SOURCE_MAP_PIN, LocationGeo
from leaderlodge.groups.locations import get_or_create_location
from leaderlodge.groups.services import add_guest_player, create_group_with_owner
from leaderlodge.groups.sync_locations import sync_group_locations


@pytest.fixture
def user(db):
    return User.objects.create_user(username="david", password="test-pass-123")


def _geo(lat: float, lon: float, place_id: str = "") -> LocationGeo:
    return LocationGeo(
        lat=lat,
        lon=lon,
        place_id=place_id,
        geocode_source=GEOCODE_SOURCE_MAP_PIN,
        city="Los Angeles",
        state="CA",
        country="US",
    )


def _record_at(user, group, location, player):
    other = add_guest_player(group=group, display_name="Other")
    return record_game(
        user=user,
        group=group,
        game_type_code="dominos",
        played_on=date(2024, 1, 15),
        participants=[
            ParticipantInput(
                player=player,
                score=100,
                result=GameParticipantResult.Result.WIN,
                placement=1,
            ),
            ParticipantInput(
                player=other,
                score=50,
                result=GameParticipantResult.Result.PLAYED,
                placement=2,
            ),
        ],
        location=location,
    )


@pytest.mark.django_db
def test_sync_overwrites_name_and_geo(user):
    src = create_group_with_owner(user=user, name="manpearl")
    dst = create_group_with_owner(user=user, name="Sync Dest")

    src_loc = get_or_create_location(
        library=src.location_library,
        name="Preston Way",
        geo=_geo(34.1, -118.5, place_id="pid-preston"),
    )
    dst_loc = get_or_create_location(
        library=dst.location_library,
        name="Home",
        geo=_geo(33.0, -117.0, place_id="pid-preston"),
    )

    summary = sync_group_locations(source_group=src, dest_group=dst, dry_run=False)

    dst_loc.refresh_from_db()
    assert dst_loc.name == "Preston Way"
    assert dst_loc.lat == 34.1
    assert dst_loc.lon == -118.5
    assert dst_loc.place_id == "pid-preston"
    assert summary.updated == 1
    assert src_loc.pk != dst_loc.pk


@pytest.mark.django_db
def test_sync_skips_missing_dst_location(user):
    src = create_group_with_owner(user=user, name="manpearl")
    dst = create_group_with_owner(user=user, name="Sync Dest")
    get_or_create_location(
        library=src.location_library,
        name="Only In Src",
        geo=_geo(34.0, -118.0, place_id="pid-only"),
    )
    get_or_create_location(library=dst.location_library, name="Unrelated")

    summary = sync_group_locations(source_group=src, dest_group=dst, dry_run=False)

    assert "Only In Src" in summary.skipped_src
    assert summary.updated == 0
    assert summary.combined == 0


@pytest.mark.django_db
def test_sync_combines_multiple_dst_matches(user):
    src = create_group_with_owner(user=user, name="manpearl")
    dst = create_group_with_owner(user=user, name="Sync Dest")
    player = add_guest_player(group=dst, display_name="Pat")

    get_or_create_location(
        library=src.location_library,
        name="Café 50's, WLA",
        geo=_geo(34.05, -118.45, place_id="pid-cafe"),
    )
    keeper = get_or_create_location(
        library=dst.location_library,
        name="Café 50's, WLA",
    )
    extra = get_or_create_location(
        library=dst.location_library,
        name="Cafe 50s",
        geo=_geo(1.0, 2.0, place_id="pid-cafe"),
    )
    _record_at(user, dst, extra, player)

    summary = sync_group_locations(source_group=src, dest_group=dst, dry_run=False)

    assert summary.combined == 1
    keeper.refresh_from_db()
    assert keeper.name == "Café 50's, WLA"
    assert keeper.lat == 34.05
    assert keeper.lon == -118.45
    assert not dst.location_library.locations.filter(pk=extra.pk).exists()
    assert Game.objects.filter(location=keeper).count() == 1


@pytest.mark.django_db
def test_sync_dry_run_writes_nothing(user):
    src = create_group_with_owner(user=user, name="manpearl")
    dst = create_group_with_owner(user=user, name="Sync Dest")
    get_or_create_location(
        library=src.location_library,
        name="Preston Way",
        geo=_geo(34.1, -118.5, place_id="pid-x"),
    )
    dst_loc = get_or_create_location(
        library=dst.location_library,
        name="Home",
        geo=_geo(33.0, -117.0, place_id="pid-x"),
    )

    summary = sync_group_locations(source_group=src, dest_group=dst, dry_run=True)

    assert summary.dry_run is True
    assert summary.updated == 1
    dst_loc.refresh_from_db()
    assert dst_loc.name == "Home"
    assert dst_loc.lat == 33.0


@pytest.mark.django_db
def test_sync_command_cli(user, capsys):
    src = create_group_with_owner(user=user, name="manpearl")
    dst = create_group_with_owner(user=user, name="Sync Dest")
    get_or_create_location(
        library=src.location_library,
        name="Preston Way",
        geo=_geo(34.1, -118.5, place_id="pid-cli"),
    )
    get_or_create_location(
        library=dst.location_library,
        name="Home",
        geo=_geo(33.0, -117.0, place_id="pid-cli"),
    )

    call_command("sync_group_locations", "--src", "manpearl", "--dst", "Sync Dest")
    out = capsys.readouterr().out
    assert "combined=0" in out
    assert "updated=1" in out
