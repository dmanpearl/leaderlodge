import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from leaderlodge.games.list_table import (
    build_game_list_table,
)
from leaderlodge.games.scoring import assign_results_from_scores
from leaderlodge.games.services import ParticipantInput, record_game
from leaderlodge.groups.services import add_guest_player, create_group_with_owner
from leaderlodge.groups.teams import resolve_side_player
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
def test_game_list_shows_weight_column_when_game_type_filtered(client, user, group):
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
    assert "game-list-stats-game-icon" in games_table
    assert "game-types/dominos.png" in games_table
    assert "2×" in games_table
    assert games_table.count("game-list-weight-badge") == 1


@pytest.mark.django_db
def test_game_list_splits_team_column_headers(client, user, group):
    owner = group.players.get(linked_user=user)
    nancy = add_guest_player(group=group, display_name="Nancy")
    zach = add_guest_player(group=group, display_name="Zach")
    opponent = add_guest_player(group=group, display_name="Opponent")
    team = resolve_side_player(group=group, members=[nancy, zach])

    rows = [
        {"player": team, "score": 11},
        {"player": opponent, "score": 5},
    ]
    assign_results_from_scores(rows, "pickleball")
    record_game(
        user=user,
        group=group,
        game_type_code="pickleball",
        played_on="2026-01-15",
        score_type="traditional",
        participants=[
            ParticipantInput(
                player=row["player"],
                score=row["score"],
                result=row["result"],
                placement=row["placement"],
            )
            for row in rows
        ],
    )

    client.force_login(user)
    response = client.get(
        reverse("games:list"),
        {"group": str(group.pk), "game_type": "pickleball"},
    )
    content = response.content.decode()
    games_table = content.split("game-list-table ", 1)[1].split("</table>", 1)[0]

    assert response.status_code == 200
    assert "game-list-player-col-label-line" in games_table
    assert '<span class="game-list-player-col-label-line">Nancy</span>' in games_table
    assert '<span class="game-list-player-col-label-line">Zach</span>' in games_table
    assert "game-list-player-col-header" in games_table

    detail_url = reverse("leaderboards:detail")
    assert (
        f'href="{detail_url}?group={group.pk}&amp;game_type_code=pickleball&amp;player={team.pk}"'
        in games_table
    )
    assert (
        f'href="{detail_url}?group={group.pk}&amp;game_type_code=pickleball&amp;player={opponent.pk}"'
        in games_table
    )


@pytest.mark.django_db
def test_game_list_column_header_links_to_rank_detail(client, user, group):
    pat = group.players.get(display_name="Pat")

    client.force_login(user)
    client.post(reverse("games:create"), _load_roster_post(group))
    client.post(reverse("games:create"), _save_game_post(group))

    response = client.get(
        reverse("games:list"),
        {"group": str(group.pk), "game_type": "dominos"},
    )
    content = response.content.decode()

    assert response.status_code == 200
    detail_url = reverse("leaderboards:detail")
    assert (
        f'href="{detail_url}?group={group.pk}&amp;type=dominos&amp;player={pat.pk}"'
        in content
    )
    assert "game-list-player-col-header-link" in content
