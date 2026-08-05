import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from leaderlodge.games.models import Game
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
    assert 'aria-label="New game"' in content
    assert "record-again-new" in content
    assert "record-again-new__label" in content
    assert "Pick" in content
    assert "Reuse" in content
    assert "Reuse Players" not in content
    assert f"/games/new/?pick_from={game.pk}" in content
    assert f"/games/new/?reuse_from={game.pk}" in content


@pytest.mark.django_db
def test_record_again_hidden_without_query_param(client, user, group):
    client.force_login(user)
    _record_game(client, group)
    game = Game.objects.get(group=group)

    content = client.get(
        reverse("games:detail", kwargs={"pk": game.pk})
    ).content.decode()
    assert 'aria-label="New game"' not in content
    assert "Reuse Players" not in content


@pytest.mark.django_db
def test_pick_from_opens_record_form_with_same_location(client, user, group):
    client.force_login(user)
    client.post(reverse("games:create"), _load_roster_post(group))
    save = _save_game_post(group)
    save["location_name"] = "Patio"
    client.post(reverse("games:create"), save)
    game = Game.objects.get(group=group)
    assert game.location is not None
    assert game.location.name == "Patio"

    response = client.get(
        reverse("games:create"),
        {"pick_from": str(game.pk)},
    )
    content = response.content.decode()
    assert response.status_code == 200
    assert response.context["show_roster"] is True
    assert response.context["location_name"] == "Patio"
    assert 'name="location_name" value="Patio"' in content
    assert "Patio" in content
    assert "Type player" in content
    assert "is-player-picker-collapsed" not in content
    assert response.context["participant_rows"] == []
    assert response.context["form"].initial.get("location_name") == "Patio"
    assert response.context["form"].initial.get("group") == game.group_id
    assert response.context["form"].initial.get("game_type_code") == game.game_type_code


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
    assert "Type player" in content
    assert players[0].display_label in content
    assert players[1].display_label in content
    assert "game-record-score-input" in content
    assert "is-player-picker-collapsed" in content
    assert "data-player-picker-expand" in content
    assert "hidden" in _expanded_tag(content)
    assert "bi-chevron-down" not in content


@pytest.mark.django_db
def test_pick_players_starts_with_add_player_expanded(client, user, group):
    client.force_login(user)
    response = client.post(reverse("games:create"), _load_roster_post(group))
    content = response.content.decode()
    assert response.status_code == 200
    assert "is-player-picker-collapsed" not in content
    assert "Type player" in content
    assert 'autocomplete="ll-player"' in content
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
    assert "Type player" not in content
