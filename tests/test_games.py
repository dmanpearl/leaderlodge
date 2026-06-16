import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone

from leaderlodge.games.models import Game, GameParticipantResult
from leaderlodge.groups.services import add_guest_player, create_group_with_owner


@pytest.fixture
def user(db):
    return User.objects.create_user(username="david", password="test-pass-123")


@pytest.fixture
def group(user):
    group = create_group_with_owner(user=user, name="Dom Club")
    add_guest_player(group=group, display_name="Pat")
    return group


def _save_game_post(
    group,
    *,
    game_type_code="dominos",
    players_played=None,
    scores=None,
):
    players = list(group.players.order_by("pk"))
    if players_played is None:
        players_played = players[:2]
    if scores is None:
        scores = {players_played[0].pk: 30, players_played[1].pk: 20}

    data = {
        "action": "save",
        "group": str(group.pk),
        "game_type_code": game_type_code,
        "played_on": timezone.localdate().isoformat(),
    }
    for player in players:
        if player in players_played:
            data[f"play_{player.pk}"] = "on"
            data[f"score_{player.pk}"] = str(scores.get(player.pk, 0))
    return data


def _load_roster_post(group, *, game_type_code="dominos"):
    return {
        "action": "load_roster",
        "group": str(group.pk),
        "game_type_code": game_type_code,
        "played_on": timezone.localdate().isoformat(),
    }


@pytest.mark.django_db
def test_record_dominos_game(client, user, group):
    client.force_login(user)
    client.post(reverse("games:create"), _load_roster_post(group))
    response = client.post(reverse("games:create"), _save_game_post(group))

    assert response.status_code == 302
    game = Game.objects.get(group=group)
    winner = game.participant_results.get(result=GameParticipantResult.Result.WIN)
    assert winner.score == 30


@pytest.mark.django_db
def test_record_dominos_tie(client, user, group):
    players = list(group.players.order_by("pk"))
    data = _save_game_post(
        group,
        players_played=players[:2],
        scores={players[0].pk: 20, players[1].pk: 20},
    )
    client.force_login(user)
    client.post(reverse("games:create"), _load_roster_post(group))
    response = client.post(reverse("games:create"), data)
    assert response.status_code == 302

    game = Game.objects.get()
    assert (
        game.participant_results.filter(result=GameParticipantResult.Result.TIE).count()
        == 2
    )


@pytest.mark.django_db
def test_record_progressive_rummy_tied_losers(client, user, group):
    players = list(group.players.order_by("pk"))
    while len(players) < 3:
        players.append(
            add_guest_player(group=group, display_name=f"Guest{len(players)}")
        )

    data = _save_game_post(
        group,
        game_type_code="progressiverummy",
        players_played=players[:3],
        scores={players[0].pk: 10, players[1].pk: 50, players[2].pk: 50},
    )
    client.force_login(user)
    client.post(
        reverse("games:create"),
        _load_roster_post(group, game_type_code="progressiverummy"),
    )
    response = client.post(reverse("games:create"), data)
    assert response.status_code == 302

    game = Game.objects.get(game_type_code="progressiverummy")
    assert (
        game.participant_results.filter(
            result=GameParticipantResult.Result.LOSS
        ).count()
        == 2
    )


@pytest.mark.django_db
def test_record_dominos_double_game(client, user, group):
    players = list(group.players.order_by("pk"))
    while len(players) < 2:
        players.append(
            add_guest_player(group=group, display_name=f"Guest{len(players)}")
        )
    data = _save_game_post(
        group,
        players_played=players[:2],
        scores={players[0].pk: 77, players[1].pk: 76},
    )
    client.force_login(user)
    client.post(reverse("games:create"), _load_roster_post(group))
    response = client.post(reverse("games:create"), data)
    assert response.status_code == 302

    game = Game.objects.get()
    assert game.double_weight == 2
    assert (
        "Double game"
        in client.get(reverse("games:detail", kwargs={"pk": game.pk})).content.decode()
    )


@pytest.mark.django_db
def test_auto_select_single_group(client, user, group):
    client.force_login(user)
    response = client.get(reverse("games:create"))
    assert response.status_code == 200
    content = response.content.decode()
    assert "Dom Club" in content
    assert "Choose a game" in content
    assert "Load roster" in content
    assert 'id="game-record-form"' not in content


@pytest.mark.django_db
def test_load_roster_requires_game_type(client, user, group):
    client.force_login(user)
    response = client.post(
        reverse("games:create"),
        {
            "action": "load_roster",
            "group": str(group.pk),
            "game_type_code": "",
            "played_on": timezone.localdate().isoformat(),
        },
    )
    assert response.status_code == 200
    assert 'id="game-record-form"' not in response.content.decode()


@pytest.mark.django_db
def test_load_roster_shows_formatted_date(client, user, group):
    client.force_login(user)
    response = client.post(reverse("games:create"), _load_roster_post(group))
    content = response.content.decode()
    assert response.status_code == 200
    assert "localdate" not in content
    assert "Change group or game" in content
    assert 'id="game-record-form"' in content


@pytest.mark.django_db
def test_setup_mode_hides_roster(client, user, group):
    client.force_login(user)
    response = client.get(reverse("games:create"), {"setup": "1"})
    assert response.status_code == 200
    content = response.content.decode()
    assert 'id="game-record-form"' not in content
    assert "Load roster" in content


@pytest.mark.django_db
def test_game_detail_for_member(client, user, group):
    client.force_login(user)
    client.post(reverse("games:create"), _load_roster_post(group))
    client.post(reverse("games:create"), _save_game_post(group))
    game = Game.objects.get()
    response = client.get(reverse("games:detail", kwargs={"pk": game.pk}))

    assert response.status_code == 200
    assert "Dom Club" in response.content.decode()
