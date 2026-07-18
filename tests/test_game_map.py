import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone

from leaderlodge.games.map_data import build_map_features, map_geojson_collection
from leaderlodge.games.models import Game, GameParticipantResult
from leaderlodge.groups.location_geo import (
    GEOCODE_SOURCE_PLACES_LOOKUP,
    LocationGeo,
)
from leaderlodge.groups.locations import get_or_create_location
from leaderlodge.groups.services import add_guest_player, create_group_with_owner


@pytest.fixture
def user(db):
    return User.objects.create_user(username="mapper", password="test-pass-123")


@pytest.fixture
def group(user):
    group = create_group_with_owner(user=user, name="Map Club")
    add_guest_player(group=group, display_name="Pat")
    add_guest_player(group=group, display_name="Sam")
    return group


def _make_game(user, group, location, game_type_code="dominos"):
    players = list(group.players.order_by("pk"))
    game = Game.objects.create(
        group=group,
        game_type_code=game_type_code,
        played_on=timezone.localdate(),
        recorded_by=user,
        player_count=2,
        location=location,
    )
    GameParticipantResult.objects.create(
        game=game,
        player=players[0],
        score=30,
        result=GameParticipantResult.Result.WIN,
        placement=0,
    )
    GameParticipantResult.objects.create(
        game=game,
        player=players[1],
        score=20,
        result=GameParticipantResult.Result.PLAYED,
        placement=1,
    )
    return game


@pytest.mark.django_db
def test_build_map_features_includes_geocoded_venues(user, group):
    parlor = get_or_create_location(
        library=group.location_library,
        name="The Parlor",
        geo=LocationGeo(
            lat=34.05,
            lon=-118.25,
            city="Los Angeles",
            state="CA",
            country="US",
            geocode_source=GEOCODE_SOURCE_PLACES_LOOKUP,
        ),
    )
    get_or_create_location(library=group.location_library, name="No Pin Yet")
    _make_game(user, group, parlor)

    features = build_map_features(group=group)
    assert len(features) == 1
    feature = features[0]
    assert feature["geometry"]["coordinates"] == [-118.25, 34.05]
    assert feature["properties"]["name"] == "The Parlor"
    assert feature["properties"]["total_games"] == 1
    assert feature["properties"]["game_counts"]["dominos"] == 1

    collection = map_geojson_collection(features)
    assert collection["type"] == "FeatureCollection"
    assert len(collection["features"]) == 1


@pytest.mark.django_db
def test_build_map_features_filters_by_country_and_bbox(user, group):
    ca = get_or_create_location(
        library=group.location_library,
        name="LA Spot",
        geo=LocationGeo(
            lat=34.05,
            lon=-118.25,
            city="Los Angeles",
            state="CA",
            country="US",
            geocode_source=GEOCODE_SOURCE_PLACES_LOOKUP,
        ),
    )
    on = get_or_create_location(
        library=group.location_library,
        name="Toronto Spot",
        geo=LocationGeo(
            lat=43.65,
            lon=-79.38,
            city="Toronto",
            state="ON",
            country="CA",
            geocode_source=GEOCODE_SOURCE_PLACES_LOOKUP,
        ),
    )
    _make_game(user, group, ca)
    _make_game(user, group, on)

    us_only = build_map_features(group=group, country="US")
    assert len(us_only) == 1
    assert us_only[0]["properties"]["name"] == "LA Spot"

    bbox_la = build_map_features(
        group=group,
        bbox=(-119.0, 33.0, -117.0, 35.0),
    )
    assert len(bbox_la) == 1
    assert bbox_la[0]["properties"]["name"] == "LA Spot"


@pytest.mark.django_db
def test_map_api_accepts_bbox_and_country(client, user, group, settings):
    from leaderlodge.games.map_data import map_country_choices, map_geo_cascade_tree

    settings.GOOGLE_PLACES_API_KEY = "test-browser-key"
    parlor = get_or_create_location(
        library=group.location_library,
        name="The Parlor",
        geo=LocationGeo(
            lat=34.05,
            lon=-118.25,
            city="Los Angeles",
            state="CA",
            country="US",
            geocode_source=GEOCODE_SOURCE_PLACES_LOOKUP,
        ),
    )
    _make_game(user, group, parlor)

    assert map_country_choices(group) == ["US"]
    tree = map_geo_cascade_tree(group)
    assert tree["US"]["CA"] == ["Los Angeles"]

    client.force_login(user)
    page = client.get(reverse("games:map"), {"group": group.pk})
    assert page.status_code == 200
    assert b'id="map-country-select"' in page.content
    assert b"map-geo-cascade-tree" in page.content

    api = client.get(
        reverse("map_locations"),
        {
            "group": group.pk,
            "country": "US",
            "bbox": "-119,33,-117,35",
        },
    )
    assert api.status_code == 200
    assert len(api.json()["features"]) == 1

    empty = client.get(
        reverse("map_locations"),
        {
            "group": group.pk,
            "bbox": "0,0,1,1",
        },
    )
    assert empty.status_code == 200
    assert empty.json()["features"] == []


@pytest.mark.django_db
def test_game_map_page_and_api(client, user, group, settings):
    settings.GOOGLE_PLACES_API_KEY = "test-browser-key"
    parlor = get_or_create_location(
        library=group.location_library,
        name="The Parlor",
        geo=LocationGeo(
            lat=34.05,
            lon=-118.25,
            city="Los Angeles",
            state="CA",
            country="US",
            geocode_source=GEOCODE_SOURCE_PLACES_LOOKUP,
        ),
    )
    _make_game(user, group, parlor)

    client.force_login(user)
    page = client.get(reverse("games:map"), {"group": group.pk})
    assert page.status_code == 200
    assert b"game-map-canvas" in page.content
    assert b"The Parlor" in page.content
    detail_template = page.context["location_detail_url_template"]
    assert "__LOC__" in detail_template
    assert str(group.pk) in detail_template
    assert reverse(
        "groups:location_detail",
        kwargs={"pk": group.pk, "loc_pk": parlor.pk},
    ) == detail_template.replace("__LOC__", str(parlor.pk))

    api = client.get(reverse("map_locations"), {"group": group.pk})
    assert api.status_code == 200
    payload = api.json()
    assert payload["type"] == "FeatureCollection"
    assert len(payload["features"]) == 1


@pytest.mark.django_db
def test_anonymous_can_open_demo_map(client, settings, db):
    settings.DEMO_MODE_ENABLED = True
    settings.GOOGLE_PLACES_API_KEY = "test-browser-key"
    owner = User.objects.create_user(username="demo-owner", password="x")
    demo = create_group_with_owner(user=owner, name="Demo")
    demo.is_demo = True
    demo.save(update_fields=["is_demo"])
    add_guest_player(group=demo, display_name="Pat")
    add_guest_player(group=demo, display_name="Sam")
    parlor = get_or_create_location(
        library=demo.location_library,
        name="Demo Cafe",
        geo=LocationGeo(
            lat=34.0,
            lon=-118.4,
            city="Los Angeles",
            state="CA",
            geocode_source=GEOCODE_SOURCE_PLACES_LOOKUP,
        ),
    )
    _make_game(owner, demo, parlor)

    response = client.get(reverse("games:map"))
    assert response.status_code in (200, 302)
    if response.status_code == 302:
        response = client.get(response["Location"])
    assert response.status_code == 200
    assert b"Map" in response.content


@pytest.mark.django_db
def test_leaderboard_location_filter(client, user, group):
    parlor = get_or_create_location(
        library=group.location_library,
        name="The Parlor",
        geo=LocationGeo(
            lat=34.05,
            lon=-118.25,
            geocode_source=GEOCODE_SOURCE_PLACES_LOOKUP,
        ),
    )
    other = get_or_create_location(
        library=group.location_library,
        name="Elsewhere",
        geo=LocationGeo(
            lat=34.1,
            lon=-118.3,
            geocode_source=GEOCODE_SOURCE_PLACES_LOOKUP,
        ),
    )
    _make_game(user, group, parlor)
    _make_game(user, group, other)

    client.force_login(user)
    response = client.get(
        reverse("leaderboards:index"),
        {
            "group": group.pk,
            "game_type_code": "dominos",
            "location": parlor.pk,
        },
    )
    assert response.status_code == 200
    assert response.context["selected_location_id"] == parlor.pk
    assert b'id="leaderboard-location"' in response.content
