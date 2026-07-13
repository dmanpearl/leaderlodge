import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from leaderlodge.games.models import Game
from leaderlodge.groups.services import add_guest_player, create_group_with_owner
from tests.test_games import _load_roster_post, _reuse_roster_post, _save_game_post


@pytest.fixture
def user(db):
    return User.objects.create_user(username="david", password="test-pass-123")


@pytest.fixture
def group(user):
    group = create_group_with_owner(user=user, name="Dom Club")
    add_guest_player(group=group, display_name="Pat")
    return group


def _record_game(client, group):
    client.post(reverse("games:create"), _load_roster_post(group))
    return client.post(reverse("games:create"), _save_game_post(group))


def _expanded_tag(content: str) -> str:
    return content.split('id="player-picker-expanded"', 1)[1].split(">", 1)[0]


@pytest.mark.django_db
def test_save_game_detail_shows_record_again(client, user, group):
    client.force_login(user)
    response = _record_game(client, group)
    game = Game.objects.get(group=group)
    assert response.status_code == 302
    detail_url = reverse("games:detail", kwargs={"pk": game.pk})
    assert response["Location"] == f"{detail_url}?record_again=1"

    detail = client.get(response["Location"])
    content = detail.content.decode()
    assert detail.status_code == 200
    assert "+ Reuse Players" in content
    assert f"/games/new/?reuse_from={game.pk}" in content


@pytest.mark.django_db
def test_record_again_hidden_without_query_param(client, user, group):
    client.force_login(user)
    _record_game(client, group)
    game = Game.objects.get(group=group)

    content = client.get(
        reverse("games:detail", kwargs={"pk": game.pk})
    ).content.decode()
    assert "+ Reuse Players" not in content


@pytest.mark.django_db
def test_record_again_visible_with_query_param_on_refresh(client, user, group):
    client.force_login(user)
    _record_game(client, group)
    game = Game.objects.get(group=group)
    detail_url = reverse("games:detail", kwargs={"pk": game.pk}) + "?record_again=1"

    first = client.get(detail_url)
    second = client.get(detail_url)
    assert "+ Reuse Players" in first.content.decode()
    assert "+ Reuse Players" in second.content.decode()


@pytest.mark.django_db
def test_reuse_from_opens_record_form_with_players_collapsed(client, user, group):
    client.force_login(user)
    _record_game(client, group)
    game = Game.objects.get(group=group)
    players = list(group.players.order_by("pk")[:2])

    response = client.get(
        reverse("games:create"),
        {"reuse_from": str(game.pk)},
    )
    content = response.content.decode()
    assert response.status_code == 200
    assert "Type player name" in content
    assert players[0].display_label in content
    assert players[1].display_label in content
    assert "game-record-score-input" in content
    assert "is-player-picker-collapsed" in content
    assert "data-player-picker-expand" in content
    assert "hidden" in _expanded_tag(content)
    assert "bi-chevron-down" not in content


@pytest.mark.django_db
def test_reuse_roster_starts_with_add_player_collapsed(client, user, group):
    client.force_login(user)
    client.post(reverse("games:create"), _load_roster_post(group))
    client.post(reverse("games:create"), _save_game_post(group))
    response = client.post(reverse("games:create"), _reuse_roster_post(group))
    content = response.content.decode()
    assert response.status_code == 200
    assert "is-player-picker-collapsed" in content
    assert "Type player name" in content
    assert "hidden" in _expanded_tag(content)


@pytest.mark.django_db
def test_pick_players_starts_with_add_player_expanded(client, user, group):
    client.force_login(user)
    response = client.post(reverse("games:create"), _load_roster_post(group))
    content = response.content.decode()
    assert response.status_code == 200
    assert "is-player-picker-collapsed" not in content
    assert "Type player name" in content
    assert "data-player-picker-expand" in content
    assert "hidden" not in _expanded_tag(content)


@pytest.mark.django_db
def test_reuse_from_denied_for_non_member(client, user, group):
    outsider = User.objects.create_user(username="outsider", password="test-pass-123")
    client.force_login(user)
    _record_game(client, group)
    game = Game.objects.get(group=group)

    client.force_login(outsider)
    response = client.get(
        reverse("games:create"),
        {"reuse_from": str(game.pk)},
    )
    content = response.content.decode()
    assert response.status_code == 200
    assert "Pick Players" in content
    assert "Type player name" not in content
