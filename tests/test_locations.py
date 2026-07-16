import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from leaderlodge.games.models import Game
from leaderlodge.groups.locations import (
    find_fuzzy_location_match,
    get_or_create_location,
    locations_for_group,
    normalize_for_fuzzy_match,
    normalize_location_name,
    resolve_game_location,
    score_location_match,
)
from leaderlodge.groups.models import Location, LocationLibrary
from leaderlodge.groups.services import add_guest_player, create_group_with_owner
from tests.test_games import _load_roster_post, _save_game_post


@pytest.fixture
def user(db):
    return User.objects.create_user(username="david", password="test-pass-123")


@pytest.mark.django_db
def test_create_group_creates_location_library(user):
    group = create_group_with_owner(user=user, name="Dom Club")

    assert group.location_library is not None
    assert group.location_library.name == "Dom Club places"
    assert group.location_library.created_by == user


@pytest.mark.django_db
def test_normalize_location_name():
    assert normalize_location_name("  Nancy's   House  ") == "nancy's house"
    assert normalize_location_name("Zinqué") == "zinque"
    assert normalize_location_name("  Café   Noir  ") == "cafe noir"


@pytest.mark.django_db
def test_normalize_for_fuzzy_match_strips_punctuation():
    assert normalize_for_fuzzy_match("Zinque, Venice") == "zinque venice"


@pytest.mark.django_db
def test_get_or_create_location_deduplicates_accents(user):
    group = create_group_with_owner(user=user, name="Dom Club")
    library = group.location_library

    first = get_or_create_location(library=library, name="Zinque")
    second = get_or_create_location(library=library, name="Zinqué")

    assert first.pk == second.pk
    assert Location.objects.filter(library=library).count() == 1
    assert second.name == "Zinqué"


@pytest.mark.django_db
def test_get_or_create_location_does_not_merge_shorter_prefix(user):
    group = create_group_with_owner(user=user, name="Dom Club")
    library = group.location_library

    first = get_or_create_location(library=library, name="Preston - Passover")
    second = get_or_create_location(library=library, name="Preston")

    assert first.pk != second.pk
    assert Location.objects.filter(library=library).count() == 2
    assert second.name == "Preston"


@pytest.mark.django_db
def test_get_or_create_location_fuzzy_merges_longer_extensions(user):
    group = create_group_with_owner(user=user, name="Dom Club")
    library = group.location_library

    first = get_or_create_location(library=library, name="Zinque")
    second = get_or_create_location(library=library, name="Zinque, Venice")

    assert first.pk == second.pk
    assert Location.objects.filter(library=library).count() == 1
    assert second.name == "Zinque, Venice"


@pytest.mark.django_db
def test_get_or_create_location_fuzzy_merges_punctuation_variants(user):
    group = create_group_with_owner(user=user, name="Dom Club")
    library = group.location_library

    first = get_or_create_location(library=library, name="Zinque, Venice")
    second = get_or_create_location(library=library, name="Zinque Venice")

    assert first.pk == second.pk
    assert Location.objects.filter(library=library).count() == 1


@pytest.mark.django_db
def test_find_fuzzy_location_match_returns_none_when_ambiguous(user):
    group = create_group_with_owner(user=user, name="Dom Club")
    library = group.location_library

    get_or_create_location(library=library, name="North Beach")
    get_or_create_location(library=library, name="South Beach")

    match = find_fuzzy_location_match(library=library, cleaned="Beach")
    assert match is None


def test_score_location_match_prefers_longer_extension():
    assert score_location_match("zinque venice", "zinque") > score_location_match(
        "zinque venice", "superior zinque"
    )
    assert score_location_match("zinque", "zinque venice") == -1


@pytest.mark.django_db
def test_get_or_create_location_deduplicates_case(user):
    group = create_group_with_owner(user=user, name="Dom Club")
    library = group.location_library

    first = get_or_create_location(library=library, name="Nancy's House")
    second = get_or_create_location(library=library, name="nancy's house")

    assert first.pk == second.pk
    assert Location.objects.filter(library=library).count() == 1


@pytest.mark.django_db
def test_groups_can_share_location_library(user):
    family = create_group_with_owner(user=user, name="Family")
    friends = create_group_with_owner(user=user, name="Friends")

    friends.location_library = family.location_library
    friends.save(update_fields=["location_library"])

    location = get_or_create_location(
        library=family.location_library,
        name="Zinque",
    )

    assert location in locations_for_group(friends)
    assert family.location_library_id == friends.location_library_id


@pytest.mark.django_db
def test_group_locations_api(client, user):
    group = create_group_with_owner(user=user, name="Dom Club")
    get_or_create_location(library=group.location_library, name="Nancy's House")

    client.force_login(user)
    response = client.get(reverse("groups:locations", kwargs={"pk": group.pk}))

    assert response.status_code == 200
    assert response.json() == {"locations": [{"name": "Nancy's House"}]}


@pytest.mark.django_db
def test_group_locations_api_requires_membership(client, user):
    group = create_group_with_owner(user=user, name="Dom Club")
    stranger = User.objects.create_user(username="stranger", password="pass")

    client.force_login(stranger)
    response = client.get(reverse("groups:locations", kwargs={"pk": group.pk}))

    assert response.status_code == 404


@pytest.mark.django_db
def test_record_game_creates_distinct_shorter_location(client, user):
    group = create_group_with_owner(user=user, name="Dom Club")
    add_guest_player(group=group, display_name="Pat")
    get_or_create_location(library=group.location_library, name="Preston - Passover")
    client.force_login(user)

    load_data = _load_roster_post(group)
    load_data["location_name"] = "Preston"
    client.post(reverse("games:create"), load_data)

    save_data = _save_game_post(group)
    save_data["location_name"] = "Preston"
    response = client.post(reverse("games:create"), save_data)

    assert response.status_code == 302
    game = Game.objects.get()
    assert game.location.name == "Preston"
    assert Location.objects.filter(library=group.location_library).count() == 2


@pytest.mark.django_db
def test_record_game_with_location(client, user):
    group = create_group_with_owner(user=user, name="Dom Club")
    add_guest_player(group=group, display_name="Pat")
    client.force_login(user)

    load_data = _load_roster_post(group)
    load_data["location_name"] = "Nancy's House"
    client.post(reverse("games:create"), load_data)

    save_data = _save_game_post(group)
    save_data["location_name"] = "Nancy's House"
    response = client.post(reverse("games:create"), save_data)

    assert response.status_code == 302
    game = Game.objects.get()
    assert game.location is not None
    assert game.location.name == "Nancy's House"
    assert game.location.library_id == group.location_library_id


@pytest.mark.django_db
def test_shared_library_location_available_to_both_groups(client, user):
    family = create_group_with_owner(user=user, name="Family")
    friends = create_group_with_owner(user=user, name="Friends")
    friends.location_library = family.location_library
    friends.save(update_fields=["location_library"])

    get_or_create_location(library=family.location_library, name="Superior Ave")

    client.force_login(user)
    add_guest_player(group=friends, display_name="Pat")
    load_data = _load_roster_post(friends)
    load_data["location_name"] = "Superior Ave"
    client.post(reverse("games:create"), load_data)

    save_data = _save_game_post(friends)
    save_data["location_name"] = "Superior Ave"
    response = client.post(reverse("games:create"), save_data)

    assert response.status_code == 302
    game = Game.objects.get(group=friends)
    assert game.location.name == "Superior Ave"


@pytest.mark.django_db
def test_resolve_game_location_returns_none_for_blank(user):
    group = create_group_with_owner(user=user, name="Dom Club")
    assert resolve_game_location(group=group, location_name="") is None


@pytest.mark.django_db
def test_location_libraries_are_not_global(user):
    other = User.objects.create_user(username="stranger", password="pass")
    create_group_with_owner(user=user, name="Mine")
    create_group_with_owner(user=other, name="Theirs")

    assert LocationLibrary.objects.count() == 2


@pytest.mark.django_db
def test_get_or_create_location_saves_places_geo(user):
    from leaderlodge.groups.location_geo import (
        GEOCODE_SOURCE_PLACES_LOOKUP,
        LocationGeo,
    )

    group = create_group_with_owner(user=user, name="Dom Club")
    geo = LocationGeo(
        lat=34.052234,
        lon=-118.243685,
        city="Los Angeles",
        state="CA",
        country="US",
        place_id="places/abc123",
        geocode_source=GEOCODE_SOURCE_PLACES_LOOKUP,
    )
    location = get_or_create_location(
        library=group.location_library,
        name="The Parlor Room, Los Angeles, CA",
        geo=geo,
    )

    location.refresh_from_db()
    assert location.lat == pytest.approx(34.052234)
    assert location.lon == pytest.approx(-118.243685)
    assert location.city == "Los Angeles"
    assert location.state == "CA"
    assert location.place_id == "places/abc123"
    assert location.geocode_source == GEOCODE_SOURCE_PLACES_LOOKUP
    assert location.geocode_at is not None


@pytest.mark.django_db
def test_get_or_create_location_does_not_overwrite_existing_coords(user):
    from leaderlodge.groups.location_geo import (
        GEOCODE_SOURCE_GPS,
        GEOCODE_SOURCE_PLACES_LOOKUP,
        LocationGeo,
    )

    group = create_group_with_owner(user=user, name="Dom Club")
    first = get_or_create_location(
        library=group.location_library,
        name="Sally's House",
        geo=LocationGeo(
            lat=34.0,
            lon=-118.0,
            geocode_source=GEOCODE_SOURCE_GPS,
        ),
    )
    second = get_or_create_location(
        library=group.location_library,
        name="Sally's House",
        geo=LocationGeo(
            lat=40.0,
            lon=-74.0,
            city="New York",
            geocode_source=GEOCODE_SOURCE_PLACES_LOOKUP,
        ),
    )

    assert first.pk == second.pk
    second.refresh_from_db()
    assert second.lat == pytest.approx(34.0)
    assert second.lon == pytest.approx(-118.0)
    assert second.city == ""
    assert second.geocode_source == GEOCODE_SOURCE_GPS


@pytest.mark.django_db
def test_get_or_create_location_fills_null_coords(user):
    from leaderlodge.groups.location_geo import (
        GEOCODE_SOURCE_GPS,
        LocationGeo,
    )

    group = create_group_with_owner(user=user, name="Dom Club")
    first = get_or_create_location(
        library=group.location_library,
        name="Sally's House",
    )
    assert first.lat is None

    second = get_or_create_location(
        library=group.location_library,
        name="Sally's House",
        geo=LocationGeo(
            lat=34.1,
            lon=-118.2,
            geocode_source=GEOCODE_SOURCE_GPS,
        ),
    )

    assert first.pk == second.pk
    second.refresh_from_db()
    assert second.lat == pytest.approx(34.1)
    assert second.geocode_source == GEOCODE_SOURCE_GPS


@pytest.mark.django_db
def test_get_or_create_location_reuses_place_id(user):
    from leaderlodge.groups.location_geo import (
        GEOCODE_SOURCE_PLACES_LOOKUP,
        LocationGeo,
    )

    group = create_group_with_owner(user=user, name="Dom Club")
    geo = LocationGeo(
        lat=34.05,
        lon=-118.25,
        place_id="places/same",
        geocode_source=GEOCODE_SOURCE_PLACES_LOOKUP,
    )
    first = get_or_create_location(
        library=group.location_library,
        name="Parlor Room",
        geo=geo,
    )
    second = get_or_create_location(
        library=group.location_library,
        name="The Parlor Room",
        geo=geo,
    )

    assert first.pk == second.pk
    assert Location.objects.filter(library=group.location_library).count() == 1


@pytest.mark.django_db
def test_combine_locations_copies_geo_onto_ungeocoded_keeper(user):
    from leaderlodge.groups.location_geo import (
        GEOCODE_SOURCE_PLACES_LOOKUP,
        LocationGeo,
    )
    from leaderlodge.groups.locations import combine_locations

    group = create_group_with_owner(user=user, name="Dom Club")
    keeper = get_or_create_location(library=group.location_library, name="Clubhouse")
    source = get_or_create_location(
        library=group.location_library,
        name="Nancy's Patio",
        geo=LocationGeo(
            lat=33.9,
            lon=-118.4,
            city="Torrance",
            state="CA",
            place_id="places/home",
            geocode_source=GEOCODE_SOURCE_PLACES_LOOKUP,
        ),
    )

    combine_locations(keeper=keeper, source=source)
    keeper.refresh_from_db()
    assert keeper.lat == pytest.approx(33.9)
    assert keeper.city == "Torrance"
    assert keeper.place_id == "places/home"
    assert not Location.objects.filter(pk=source.pk).exists()


@pytest.mark.django_db
def test_resolve_game_location_accepts_geo(user):
    from leaderlodge.groups.location_geo import (
        GEOCODE_SOURCE_PLACES_LOOKUP,
        LocationGeo,
    )

    group = create_group_with_owner(user=user, name="Dom Club")
    location = resolve_game_location(
        group=group,
        location_name="Zinque",
        geo=LocationGeo(
            lat=33.985,
            lon=-118.469,
            geocode_source=GEOCODE_SOURCE_PLACES_LOOKUP,
        ),
    )
    assert location is not None
    assert location.lat == pytest.approx(33.985)
