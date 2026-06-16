import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from leaderlodge.games.models import Game
from leaderlodge.groups.locations import (
    get_or_create_location,
    locations_for_group,
    normalize_location_name,
    resolve_game_location,
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
def test_get_or_create_location_deduplicates_accents(user):
    group = create_group_with_owner(user=user, name="Dom Club")
    library = group.location_library

    first = get_or_create_location(library=library, name="Zinque")
    second = get_or_create_location(library=library, name="Zinqué")

    assert first.pk == second.pk
    assert Location.objects.filter(library=library).count() == 1
    assert second.name == "Zinqué"


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
