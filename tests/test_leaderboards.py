import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from leaderlodge.groups.services import add_guest_player, create_group_with_owner
from leaderlodge.leaderboards.service import get_player_rankings, get_player_stats
from tests.test_games import _load_roster_post, _save_game_post


@pytest.fixture
def user(db):
    return User.objects.create_user(username="david", password="test-pass-123")


@pytest.fixture
def group(user):
    group = create_group_with_owner(user=user, name="Dom Club")
    add_guest_player(group=group, display_name="Pat")
    return group


@pytest.mark.django_db
def test_leaderboard_index_requires_login(client):
    response = client.get(reverse("leaderboards:index"))
    assert response.status_code == 302


@pytest.mark.django_db
def test_leaderboard_shows_rankings(client, user, group):
    client.force_login(user)
    client.post(reverse("games:create"), _load_roster_post(group))
    client.post(reverse("games:create"), _save_game_post(group))

    response = client.get(
        reverse("leaderboards:index"),
        {"group": str(group.pk), "game_type_code": "dominos"},
    )
    assert response.status_code == 200
    content = response.content.decode()
    assert "Dom Club" in content
    assert "Dominos" in content


@pytest.mark.django_db
def test_get_player_rankings_counts_double_weight(client, user, group):
    client.force_login(user)
    players = list(group.players.order_by("pk"))
    while len(players) < 2:
        players.append(
            add_guest_player(group=group, display_name=f"Guest{len(players)}")
        )
    client.post(reverse("games:create"), _load_roster_post(group))
    client.post(
        reverse("games:create"),
        _save_game_post(
            group,
            players_played=players[:2],
            scores={players[0].pk: 77, players[1].pk: 76},
        ),
    )

    rankings = get_player_rankings(group, game_type_code="dominos", min_games=1)
    winner = next(row for row in rankings if row.wins > 0)
    assert winner.games_played == 2
    assert winner.wins == 2


@pytest.mark.django_db
def test_get_player_stats(client, user, group):
    client.force_login(user)
    client.post(reverse("games:create"), _load_roster_post(group))
    client.post(reverse("games:create"), _save_game_post(group))

    player = group.players.order_by("pk").first()
    stats = get_player_stats(group, player)
    assert stats["dominos"]["games_played"] >= 1
