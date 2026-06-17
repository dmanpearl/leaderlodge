import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from leaderlodge.games.list_table import build_game_list_table, result_cell_class
from leaderlodge.groups.services import add_guest_player, create_group_with_owner
from tests.test_games import _load_roster_post, _save_game_post


@pytest.fixture
def user(db):
    return User.objects.create_user(username="david", password="test-pass-123")


@pytest.fixture
def group(user):
    group = create_group_with_owner(user=user, name="Dom Club")
    add_guest_player(group=group, display_name="Pat")
    return group


def test_result_cell_class():
    assert result_cell_class(result="win", is_double=False) == "game-list-cell--win"
    assert result_cell_class(result="win", is_double=True) == "game-list-cell--win-double"
    assert result_cell_class(result="loss", is_double=False) == "game-list-cell--loss"
    assert result_cell_class(result="loss", is_double=True) == "game-list-cell--loss-double"
    assert result_cell_class(result="tie", is_double=False) == "game-list-cell--tie"
    assert result_cell_class(result="played", is_double=False) == ""


@pytest.mark.django_db
def test_build_game_list_table_only_includes_players_on_page(user, group):
    other_group = create_group_with_owner(user=user, name="Other")
    add_guest_player(group=other_group, display_name="Alex")

    from django.test import Client

    client = Client()
    client.force_login(user)

    client.post(reverse("games:create"), _load_roster_post(group))
    client.post(reverse("games:create"), _save_game_post(group))

    games = list(group.games.all())
    player_columns, rows = build_game_list_table(games)

    labels = [player.display_label for player in player_columns]
    assert "Pat" in labels
    assert "Alex" not in labels
    assert len(rows) == 1
    assert len(rows[0].cells) == len(player_columns)


@pytest.mark.django_db
def test_game_list_shows_player_scores_and_result_shading(client, user, group):
    client.force_login(user)
    client.post(reverse("games:create"), _load_roster_post(group))
    client.post(reverse("games:create"), _save_game_post(group))

    response = client.get(reverse("games:list"))
    content = response.content.decode()

    assert response.status_code == 200
    assert "game-list-cell--win" in content
    assert "Pat" in content
    assert "30" in content
    assert "20" in content
