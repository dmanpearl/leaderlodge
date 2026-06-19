import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from leaderlodge.games.list_table import build_game_list_table, result_cell_class, show_weight_column
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


def test_show_weight_column():
    from leaderlodge.games.models import Game

    normal_game = Game(double_weight=1, half_weight=1)
    double_game = Game(double_weight=2, half_weight=1)
    half_game = Game(double_weight=1, half_weight=2)

    assert show_weight_column(games=[], game_type_code="dominos") is True
    assert show_weight_column(games=[], game_type_code="progressiverummy") is True
    assert show_weight_column(games=[normal_game], game_type_code="") is False
    assert show_weight_column(games=[double_game], game_type_code="") is True
    assert show_weight_column(games=[half_game], game_type_code="backgammon") is True


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

    response = client.get(reverse("games:list"), follow=True)
    content = response.content.decode()

    assert response.status_code == 200
    assert "game-list-cell--win" in content
    assert "Pat" in content
    assert "30" in content
    assert "20" in content


@pytest.mark.django_db
def test_game_list_shows_weight_column_when_game_type_filtered(client, user, group):
    players = list(group.players.order_by("pk"))
    while len(players) < 2:
        players.append(add_guest_player(group=group, display_name=f"Guest{len(players)}"))
    data = _save_game_post(
        group,
        players_played=players[:2],
        scores={players[0].pk: 77, players[1].pk: 76},
    )

    client.force_login(user)
    client.post(reverse("games:create"), _load_roster_post(group))
    client.post(reverse("games:create"), data)

    response = client.get(
        reverse("games:list"),
        {"group": str(group.pk), "game_type": "dominos"},
    )
    content = response.content.decode()
    games_table = content.split("game-list-table ", 1)[1].split("</table>", 1)[0]

    assert response.status_code == 200
    assert content.count('<th scope="col">Game</th>') == 0
    assert 'aria-label="Weight modifier"' in games_table
    assert "2×" in games_table
    assert games_table.count("game-list-weight-badge") == 1


@pytest.mark.django_db
def test_game_list_puts_weight_badges_in_weight_column(client, user, group):
    players = list(group.players.order_by("pk"))
    while len(players) < 2:
        players.append(add_guest_player(group=group, display_name=f"Guest{len(players)}"))
    data = _save_game_post(
        group,
        players_played=players[:2],
        scores={players[0].pk: 77, players[1].pk: 76},
    )

    client.force_login(user)
    client.post(reverse("games:create"), _load_roster_post(group))
    client.post(reverse("games:create"), data)

    response = client.get(
        reverse("games:list"),
        {"group": str(group.pk)},
        follow=True,
    )
    content = response.content.decode()
    games_table = content.split("game-list-table ", 1)[1].split("</table>", 1)[0]

    assert response.status_code == 200
    assert "Dominos" in content
    assert "2×" in games_table
    assert "Dominos\n                    2×" not in content.replace("\r\n", "\n")
    assert "Dominos\n                      2×" not in content.replace("\r\n", "\n")
