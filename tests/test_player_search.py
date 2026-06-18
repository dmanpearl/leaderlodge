import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from leaderlodge.groups.fuzzy import score_fuzzy_match
from leaderlodge.groups.player_search import guest_name_is_available, search_group_players
from leaderlodge.groups.services import add_guest_player, create_group_with_owner


@pytest.fixture
def user(db):
    return User.objects.create_user(username="david", password="test-pass-123")


@pytest.fixture
def group(user):
    group = create_group_with_owner(user=user, name="Dom Club")
    add_guest_player(group=group, display_name="Pat")
    return group


def test_score_fuzzy_match_prefers_prefix():
    assert score_fuzzy_match("pat", "Pat") > score_fuzzy_match("pat", "Patrick")


@pytest.mark.django_db
def test_search_group_players_matches_username(group, user):
    results = search_group_players(group, "david")
    assert any(entry["username"] == "david" for entry in results)


@pytest.mark.django_db
def test_search_group_players_matches_guest_name(group):
    results = search_group_players(group, "pat")
    assert any(entry["label"] == "Pat" and entry["kind"] == "guest" for entry in results)


@pytest.mark.django_db
def test_guest_name_is_available(group):
    assert guest_name_is_available(group, "Alex") is True
    assert guest_name_is_available(group, "Pat") is False


@pytest.mark.django_db
def test_group_players_search_api(client, user, group):
    client.force_login(user)
    response = client.get(
        reverse("groups:players_search", kwargs={"pk": group.pk}),
        {"q": "pat"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert any(item["label"] == "Pat" for item in payload["players"])


@pytest.mark.django_db
def test_group_players_search_hidden_from_non_member(client, group):
    other = User.objects.create_user(username="alice", password="test-pass-123")
    client.force_login(other)
    response = client.get(
        reverse("groups:players_search", kwargs={"pk": group.pk}),
        {"q": "pat"},
    )

    assert response.status_code == 404
