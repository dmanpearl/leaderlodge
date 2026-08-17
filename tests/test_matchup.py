import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse

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
    assert "player-type-icon" in content
    assert "bi bi-person-check player-type-icon" in content  # owner/user column
    assert "bi bi-person player-type-icon" in content  # guest column
    assert "Leaderboard rank" in content
    assert "Current streak" in content
    assert "Longest streak" in content
    assert "This game score" in content
    assert "Place" in content
    assert "Place %" in content
    assert "Points" in content
    assert "Points/Game" in content
    assert "Together points" in content
    assert "Together points/Game" in content


@pytest.mark.django_db
def test_matchup_points_and_together_points_total_and_per_game(group, user):
    players = list(group.players.order_by("pk")[:2])
    first, second = players[0], players[1]

    client = Client()
    client.force_login(user)

    _record_game(client, group, players, {first.pk: 30, second.pk: 20})
    _record_game(client, group, players, {first.pk: 35, second.pk: 15})

    game = Game.objects.filter(group=group).order_by("pk").last()
    matchup = build_matchup_view(game)

    def _display_by_player(label: str) -> dict[int, str]:
        row = next(item for item in matchup.rows if item.label == label)
        return {
            matchup.players[index].player.pk: row.cells[index].display
            for index in range(len(matchup.players))
        }

    points = _display_by_player("Points")
    points_per_game = _display_by_player("Points/Game")
    together = _display_by_player("Together points")
    together_per_game = _display_by_player("Together points/Game")

    # Game1 30/20, Game2 35/15. After game2: first 65, second 35.
    assert points[first.pk].endswith("65")
    assert points[second.pk].endswith("35")
    assert points_per_game[first.pk].endswith("32.5")
    assert points_per_game[second.pk].endswith("17.5")
    assert together[first.pk].endswith("65")
    assert together[second.pk].endswith("35")
    assert together_per_game[first.pk].endswith("32.5")
    assert together_per_game[second.pk].endswith("17.5")


@pytest.mark.django_db
def test_matchup_this_game_result_blanks_played_and_hides_unsupported_loss(group, user):
    players = list(group.players.order_by("pk")[:2])
    winner, other = players[0], players[1]

    client = Client()
    client.force_login(user)

    # Dominos: supports_loser=False, so non-winner is Played (not Loss).
    _record_game(client, group, players, {winner.pk: 30, other.pk: 20})
    game = Game.objects.filter(group=group).order_by("pk").last()
    matchup = build_matchup_view(game)
    result_row = next(row for row in matchup.rows if row.label == "This game result")
    by_player = {
        matchup.players[index].player.pk: result_row.cells[index].display
        for index in range(len(matchup.players))
    }
    assert by_player[winner.pk] == "Win"
    assert by_player[other.pk] == ""
    assert "Played" not in {cell.display for cell in result_row.cells}
    assert "Loss" not in {cell.display for cell in result_row.cells}


@pytest.mark.django_db
def test_matchup_this_game_result_shows_loss_when_supported(group, user):
    while group.players.count() < 3:
        add_guest_player(group=group, display_name=f"Extra{group.players.count()}")
    players = list(group.players.order_by("pk")[:3])
    winner, middle, loser = players[0], players[1], players[2]

    client = Client()
    client.force_login(user)

    client.post(
        reverse("games:create"),
        _load_roster_post(group, game_type_code="progressiverummy"),
    )
    client.post(
        reverse("games:create"),
        _save_game_post(
            group,
            game_type_code="progressiverummy",
            players_played=players,
            scores={winner.pk: 10, middle.pk: 40, loser.pk: 80},
        ),
    )
    game = Game.objects.filter(group=group).order_by("pk").last()
    matchup = build_matchup_view(game)
    result_row = next(row for row in matchup.rows if row.label == "This game result")
    by_player = {
        matchup.players[index].player.pk: result_row.cells[index].display
        for index in range(len(matchup.players))
    }
    assert by_player[winner.pk] == "Win"
    assert by_player[middle.pk] == ""
    assert by_player[loser.pk] == "Loss"


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


@pytest.mark.django_db
def test_matchup_streak_rows_reflect_career_through_game(group, user):
    players = list(group.players.order_by("pk")[:2])
    first, second = players[0], players[1]

    client = Client()
    client.force_login(user)

    _record_game(client, group, players, {first.pk: 30, second.pk: 20})
    _record_game(client, group, players, {first.pk: 35, second.pk: 15})
    _record_game(client, group, players, {first.pk: 20, second.pk: 30})

    game = Game.objects.filter(group=group).order_by("pk").last()
    matchup = build_matchup_view(game)
    longest = next(row for row in matchup.rows if row.label == "Longest streak")
    current = next(row for row in matchup.rows if row.label == "Current streak")

    by_player_longest = {
        matchup.players[index].player.pk: longest.cells[index].display
        for index in range(len(matchup.players))
    }
    by_player_current = {
        matchup.players[index].player.pk: current.cells[index].display
        for index in range(len(matchup.players))
    }
    # First: W W L (longest 2, current 0). Second: L L W (longest 1, current 1).
    assert by_player_longest[first.pk] == "2"
    assert by_player_current[first.pk].endswith("0")
    assert by_player_current[second.pk].endswith("1")
    assert by_player_longest[second.pk].endswith("1")
