import json
from io import StringIO
from unittest.mock import patch

import pytest
from django.contrib.auth.models import User
from django.core.management import call_command

from leaderlodge.groups.location_geo import GEOCODE_SOURCE_BACKFILL_CONFIRMED
from leaderlodge.groups.locations import get_or_create_location
from leaderlodge.groups.places_client import PlaceHit, place_hit_from_api
from leaderlodge.groups.services import create_group_with_owner


@pytest.fixture
def user(db):
    return User.objects.create_user(username="david", password="test-pass-123")


def test_place_hit_from_api_parses_address_components():
    raw = {
        "id": "ChIJabc",
        "displayName": {"text": "Café 50's"},
        "formattedAddress": "11623 Santa Monica Blvd, Los Angeles, CA 90025, USA",
        "location": {"latitude": 34.040123, "longitude": -118.465678},
        "addressComponents": [
            {
                "longText": "Los Angeles",
                "shortText": "Los Angeles",
                "types": ["locality"],
            },
            {
                "longText": "California",
                "shortText": "CA",
                "types": ["administrative_area_level_1"],
            },
            {"longText": "United States", "shortText": "US", "types": ["country"]},
            {"longText": "90025", "shortText": "90025", "types": ["postal_code"]},
            {"longText": "Santa Monica Boulevard", "types": ["route"]},
        ],
    }
    hit = place_hit_from_api(raw)
    assert hit is not None
    assert hit.place_id == "ChIJabc"
    assert hit.display_name == "Café 50's"
    assert hit.lat == 34.040123
    assert hit.lon == -118.465678
    assert hit.city == "Los Angeles"
    assert hit.state == "CA"
    assert hit.country == "US"
    assert hit.postal_code == "90025"
    assert hit.street_address == "Santa Monica Boulevard"


@pytest.mark.django_db
def test_backfill_command_assigns_keep_name(user, settings, tmp_path):
    settings.GOOGLE_PLACES_SERVER_API_KEY = "test-server-key"
    group = create_group_with_owner(user=user, name="manpearl")
    location = get_or_create_location(
        library=group.location_library,
        name="Cafe 50s",
    )
    hit = PlaceHit(
        place_id="pid-1",
        display_name="Café 50's",
        formatted_address="Los Angeles, CA",
        lat=34.04,
        lon=-118.46,
        city="Los Angeles",
        state="CA",
        country="US",
    )
    skip_file = tmp_path / "skips.json"

    with (
        patch(
            "leaderlodge.groups.management.commands.backfill_location_places.search_places_text",
            return_value=[hit],
        ),
        patch("builtins.input", side_effect=["1", "q"]),
    ):
        out = StringIO()
        call_command(
            "backfill_location_places",
            "--group",
            "manpearl",
            "--skip-file",
            str(skip_file),
            stdout=out,
        )

    location.refresh_from_db()
    assert location.name == "Cafe 50s"
    assert location.lat == 34.04
    assert location.lon == -118.46
    assert location.place_id == "pid-1"
    assert location.geocode_source == GEOCODE_SOURCE_BACKFILL_CONFIRMED
    assert "assigned=1" in out.getvalue()


@pytest.mark.django_db
def test_backfill_command_skip_remembered(user, settings, tmp_path):
    settings.GOOGLE_PLACES_SERVER_API_KEY = "test-server-key"
    group = create_group_with_owner(user=user, name="manpearl")
    location = get_or_create_location(
        library=group.location_library,
        name="Mystery Spot",
    )
    skip_file = tmp_path / "skips.json"

    with (
        patch(
            "leaderlodge.groups.management.commands.backfill_location_places.search_places_text",
            return_value=[],
        ),
        patch("builtins.input", side_effect=["s"]),
    ):
        call_command(
            "backfill_location_places",
            "--group",
            "manpearl",
            "--skip-file",
            str(skip_file),
        )

    data = json.loads(skip_file.read_text(encoding="utf-8"))
    assert location.pk in data["skipped_pks"]
    location.refresh_from_db()
    assert location.lat is None
