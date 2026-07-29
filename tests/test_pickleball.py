import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from leaderlodge.games.models import Game, GameScoreChangeLog
from leaderlodge.games.registry import (
    ScoreType,
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
def test_edit_pickleball_score_type(client, user, group):
    client.force_login(user)
    client.post(
        reverse("games:create"),
        _load_roster_post(group, game_type_code="pickleball"),
    )
    client.post(
        reverse("games:create"),
        _save_pickleball_post(group, score_type="traditional"),
    )
    game = Game.objects.get(group=group)
    participants = list(game.participant_results.order_by("pk"))
    url = reverse("games:edit_game", kwargs={"pk": game.pk})

    response = client.get(url)
    assert response.status_code == 200
    assert "Score type" in response.content.decode()

    response = client.post(
        url,
        {
            "played_on": game.played_on.isoformat(),
            "score_type": ScoreType.RALLY.value,
            f"score_{participants[0].pk}": participants[0].score,
            f"score_{participants[1].pk}": participants[1].score,
            "notes": "Imported as traditional by mistake.",
        },
    )
    assert response.status_code == 302
    game.refresh_from_db()
    assert game.score_type == ScoreType.RALLY.value
    log = GameScoreChangeLog.objects.get(game=game)
    assert log.old_snapshot["score_type"] == ScoreType.TRADITIONAL.value
    assert log.new_snapshot["score_type"] == ScoreType.RALLY.value


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
