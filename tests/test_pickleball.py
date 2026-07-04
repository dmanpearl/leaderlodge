import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from leaderlodge.games.list_table import show_weight_column
from leaderlodge.games.models import Game
from leaderlodge.games.registry import (
    ScoreType,
    get_game_type,
    normalize_score_type,
    score_type_choices_for,
)
from leaderlodge.groups.services import add_guest_player, create_group_with_owner
from tests.test_games import _load_roster_post, _save_game_post


@pytest.fixture
def user(db):
    return User.objects.create_user(username="david", password="test-pass-123")


@pytest.fixture
def group(user):
    group = create_group_with_owner(user=user, name="Pickle Club")
    add_guest_player(group=group, display_name="Pat")
    return group


def test_pickleball_registry():
    game_type = get_game_type("pickleball")
    assert game_type.name == "Pickleball"
    assert game_type.min_players == 2
    assert game_type.max_players == 3
    assert game_type.icon_filename == "pickleball.png"
    assert score_type_choices_for("pickleball") == [
        (ScoreType.TRADITIONAL.value, "Traditional"),
        (ScoreType.RALLY.value, "Rally"),
    ]


def test_normalize_score_type_defaults_to_traditional():
    assert normalize_score_type("pickleball", "") == ScoreType.TRADITIONAL.value
    assert normalize_score_type("dominos", "") == ""


def test_show_weight_column_for_pickleball():
    assert show_weight_column(games=[], game_type_code="pickleball") is True


def _save_pickleball_post(
    group, *, score_type="traditional", players_played=None, scores=None
):
    data = _save_game_post(
        group,
        game_type_code="pickleball",
        players_played=players_played,
        scores=scores,
    )
    data["score_type"] = score_type
    return data


@pytest.mark.django_db
def test_record_pickleball_traditional(client, user, group):
    client.force_login(user)
    client.post(
        reverse("games:create"),
        _load_roster_post(group, game_type_code="pickleball"),
    )
    response = client.post(
        reverse("games:create"),
        _save_pickleball_post(group, score_type="traditional"),
    )

    assert response.status_code == 302
    game = Game.objects.get(group=group)
    assert game.game_type_code == "pickleball"
    assert game.score_type == ScoreType.TRADITIONAL.value


@pytest.mark.django_db
def test_record_pickleball_rally(client, user, group):
    client.force_login(user)
    client.post(
        reverse("games:create"),
        _load_roster_post(group, game_type_code="pickleball"),
    )
    response = client.post(
        reverse("games:create"),
        _save_pickleball_post(
            group,
            score_type="rally",
            scores={
                list(group.players.order_by("pk"))[0].pk: 11,
                list(group.players.order_by("pk"))[1].pk: 7,
            },
        ),
    )

    assert response.status_code == 302
    game = Game.objects.get(group=group)
    assert game.score_type == ScoreType.RALLY.value


@pytest.mark.django_db
def test_record_pickleball_rejects_invalid_score_type(client, user, group):
    client.force_login(user)
    client.post(
        reverse("games:create"),
        _load_roster_post(group, game_type_code="pickleball"),
    )
    response = client.post(
        reverse("games:create"),
        _save_pickleball_post(group, score_type="invalid"),
    )

    assert response.status_code == 200
    assert Game.objects.count() == 0
    assert "Score type must be one of" in response.content.decode()


@pytest.mark.django_db
def test_game_list_shows_rally_badge(client, user, group):
    client.force_login(user)
    client.post(
        reverse("games:create"),
        _load_roster_post(group, game_type_code="pickleball"),
    )
    client.post(
        reverse("games:create"),
        _save_pickleball_post(group, score_type="rally"),
    )

    response = client.get(
        reverse("games:list"),
        {"group": str(group.pk), "game_type": "pickleball"},
    )
    content = response.content.decode()
    games_table = content.split("game-list-table ", 1)[1].split("</table>", 1)[0]

    assert response.status_code == 200
    assert "game-types/pickleball.png" in games_table
    assert ">R</span>" in games_table
    assert games_table.count("game-list-weight-badge") == 1


@pytest.mark.django_db
def test_game_list_hides_traditional_score_type_badge(client, user, group):
    client.force_login(user)
    client.post(
        reverse("games:create"),
        _load_roster_post(group, game_type_code="pickleball"),
    )
    client.post(
        reverse("games:create"),
        _save_pickleball_post(group, score_type="traditional"),
    )

    response = client.get(
        reverse("games:list"),
        {"group": str(group.pk), "game_type": "pickleball"},
    )
    games_table = (
        response.content.decode()
        .split("game-list-table ", 1)[1]
        .split("</table>", 1)[0]
    )

    assert ">R</span>" not in games_table
    assert "game-list-weight-badge" not in games_table


@pytest.mark.django_db
def test_record_game_form_shows_score_type_selector(client, user, group):
    client.force_login(user)
    response = client.post(
        reverse("games:create"),
        _load_roster_post(group, game_type_code="pickleball"),
    )
    content = response.content.decode()

    assert response.status_code == 200
    assert 'id="game-score-type"' in content
    assert 'value="traditional"' in content
    assert 'value="rally"' in content
