import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.urls import resolve, reverse

from leaderlodge.games.matchup import build_matchup_view
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
    add_guest_player(group=group, display_name="Sam")
    return group


def _record_game(client, group, players, scores):
    client.post(reverse("games:create"), _load_roster_post(group))
    return client.post(
        reverse("games:create"),
        _save_game_post(group, players_played=players, scores=scores),
    )


@pytest.mark.django_db
def test_save_game_redirects_to_game_detail(client, user, group):
    players = list(group.players.order_by("pk")[:2])
    client.force_login(user)
    response = _record_game(
        client,
        group,
        players,
        {players[0].pk: 30, players[1].pk: 20},
    )

    assert response.status_code == 302
    game = Game.objects.get(group=group)
    assert response["Location"] == (
        reverse("games:detail", kwargs={"pk": game.pk}) + "?record_again=1"
    )


@pytest.mark.django_db
def test_matchup_view_shows_players_and_stats(client, user, group):
    players = list(group.players.order_by("pk")[:2])
    client.force_login(user)
    _record_game(client, group, players, {players[0].pk: 30, players[1].pk: 20})
    game = Game.objects.get(group=group)

    response = client.get(reverse("games:matchup"), {"game": game.pk})
    assert response.status_code == 200
    content = response.content.decode()
    assert "Matchup" in content
    assert players[0].display_label in content
    assert players[1].display_label in content
    assert "Leaderboard rank" in content
    assert "This game score" in content
    assert "Place" in content
    assert "Place %" in content


@pytest.mark.django_db
def test_matchup_place_and_place_pct_for_this_game(group, user):
    players = list(group.players.order_by("pk")[:2])
    winner, loser = players[0], players[1]

    client = Client()
    client.force_login(user)

    _record_game(client, group, players, {winner.pk: 30, loser.pk: 20})
    _record_game(client, group, players, {winner.pk: 35, loser.pk: 15})

    game = Game.objects.filter(group=group).order_by("pk").last()
    matchup = build_matchup_view(game)

    place_row = next(row for row in matchup.rows if row.label == "Place")
    place_pct_row = next(row for row in matchup.rows if row.label == "Place %")

    place_by_player = {
        matchup.players[index].player.pk: place_row.cells[index].display
        for index in range(len(matchup.players))
    }
    assert place_by_player[winner.pk] == "1"
    assert place_by_player[loser.pk] == "2"

    loser_pct = next(
        place_pct_row.cells[index].display
        for index, column in enumerate(matchup.players)
        if column.player.pk == loser.pk
    )
    assert loser_pct == "100.0%"


@pytest.mark.django_db
def test_build_matchup_view_marks_rank_changes_after_second_game(group, user):
    players = list(group.players.order_by("pk")[:2])
    first, second = players[0], players[1]

    client = Client()
    client.force_login(user)

    _record_game(client, group, players, {first.pk: 20, second.pk: 30})
    _record_game(client, group, players, {first.pk: 35, second.pk: 15})

    game = Game.objects.filter(group=group).order_by("pk").last()
    matchup = build_matchup_view(game)
    rank_row = next(row for row in matchup.rows if row.label == "Leaderboard rank")

    changes = {
        matchup.players[index].player.pk: rank_row.cells[index].change
        for index in range(len(matchup.players))
    }
    assert changes[first.pk] == "up"
    assert changes[second.pk] == "down"
