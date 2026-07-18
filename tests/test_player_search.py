import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from leaderlodge.groups.player_search import (
    search_group_players,
)
from leaderlodge.groups.services import add_guest_player, create_group_with_owner


@pytest.fixture
def user(db):
    return User.objects.create_user(username="david", password="test-pass-123")


@pytest.fixture
def group(user):
    group = create_group_with_owner(user=user, name="Dom Club")
    add_guest_player(group=group, display_name="Pat")
    return group


@pytest.mark.django_db
def test_search_group_players_matches_username(group, user):
    results = search_group_players(group, "david")
    assert any(entry["username"] == "david" for entry in results)


@pytest.mark.django_db
def test_group_players_search_hidden_from_non_member(client, group):
    other = User.objects.create_user(username="alice", password="test-pass-123")
    client.force_login(other)
    response = client.get(
        reverse("groups:players_search", kwargs={"pk": group.pk}),
        {"q": "pat"},
    )

    assert response.status_code == 404
