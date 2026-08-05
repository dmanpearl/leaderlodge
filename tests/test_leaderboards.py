import pytest
from datetime import date
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone

from leaderlodge.games.models import GameParticipantResult
from leaderlodge.games.scoring import assign_results_from_scores
from leaderlodge.games.services import ParticipantInput, record_game
from leaderlodge.groups.services import (
    add_group_member,
    add_guest_player,
    create_group_with_owner,
)
from leaderlodge.groups.teams import resolve_side_player
from leaderlodge.leaderboards.service import get_player_rankings
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

    rankings = get_player_rankings(group, game_type_code="dominos")
    winner = next(row for row in rankings if row.wins > 0)
    assert winner.games_played == 2
    assert winner.wins == 2


@pytest.mark.django_db
def test_get_player_rankings_counts_half_weight(user, group):
    players = [
        add_guest_player(group=group, display_name="Alice"),
        add_guest_player(group=group, display_name="Bob"),
        add_guest_player(group=group, display_name="Carol"),
    ]
    rows = [
        {"player": players[0], "score": 10},
        {"player": players[1], "score": 20},
        {"player": players[2], "score": 30},
    ]
    assign_results_from_scores(rows, "progressiverummy")
    participants = [
        ParticipantInput(
            player=row["player"],
            score=row["score"],
            result=row["result"],
            placement=row["placement"],
        )
        for row in rows
    ]
    record_game(
        user=user,
        group=group,
        game_type_code="progressiverummy",
        played_on=date(2026, 1, 1),
        participants=participants,
        half_weight=2,
    )

    rankings = get_player_rankings(
        group,
        game_type_code="progressiverummy",
    )
    winner = next(row for row in rankings if row.wins > 0)
    assert winner.games_played == 0.5
    assert winner.wins == 0.5


@pytest.mark.django_db
def test_rank_detail_shows_breakdown(client, user, group):
    client.force_login(user)
    client.post(reverse("games:create"), _load_roster_post(group))
    client.post(reverse("games:create"), _save_game_post(group))

    player = group.players.order_by("pk").first()
    response = client.get(
        reverse("leaderboards:detail"),
        {
            "group": str(group.pk),
            "type": "dominos",
            "player": str(player.pk),
        },
    )
    assert response.status_code == 200
    content = response.content.decode()
    assert "Rank score" in content
    assert "Activity" in content
    assert "Scores" in content
    assert "Finish placements" in content
    assert player.display_label in content
    assert reverse("core:about_scoring") in content


@pytest.mark.django_db
def test_leaderboard_links_to_scoring_explainer(client, user, group):
    client.force_login(user)
    client.post(reverse("games:create"), _load_roster_post(group))
    client.post(reverse("games:create"), _save_game_post(group))

    response = client.get(
        reverse("leaderboards:index"),
        {"group": str(group.pk), "type": "dominos"},
    )
    assert response.status_code == 200
    assert reverse("core:about_scoring") in response.content.decode()


@pytest.mark.django_db
def test_leaderboard_shows_invite_action_for_guest(client, user, group):
    client.force_login(user)
    client.post(reverse("games:create"), _load_roster_post(group))
    client.post(reverse("games:create"), _save_game_post(group))

    guest = group.players.get(display_name="Pat")
    response = client.get(
        reverse("leaderboards:index"),
        {"group": str(group.pk), "type": "dominos"},
    )
    assert response.status_code == 200
    content = response.content.decode()
    invite_url = reverse(
        "groups:player_invite", kwargs={"pk": group.pk, "player_pk": guest.pk}
    )
    assert invite_url in content
    assert "Invite with email" in content


@pytest.mark.django_db
def test_leaderboard_hides_invite_action_for_linked_user(client, user, group):
    client.force_login(user)
    client.post(reverse("games:create"), _load_roster_post(group))
    client.post(reverse("games:create"), _save_game_post(group))

    owner_player = group.players.get(linked_user=user)
    response = client.get(
        reverse("leaderboards:index"),
        {"group": str(group.pk), "type": "dominos"},
    )
    assert response.status_code == 200
    content = response.content.decode()
    invite_url = reverse(
        "groups:player_invite", kwargs={"pk": group.pk, "player_pk": owner_player.pk}
    )
    assert invite_url not in content


@pytest.mark.django_db
def test_leaderboard_hides_invite_action_for_non_manager(client, user, group):
    client.force_login(user)
    client.post(reverse("games:create"), _load_roster_post(group))
    client.post(reverse("games:create"), _save_game_post(group))

    guest = group.players.get(display_name="Pat")
    viewer = User.objects.create_user(username="viewer", password="test-pass-123")
    add_group_member(group=group, user=viewer)
    client.force_login(viewer)

    response = client.get(
        reverse("leaderboards:index"),
        {"group": str(group.pk), "type": "dominos"},
    )
    assert response.status_code == 200
    content = response.content.decode()
    invite_url = reverse(
        "groups:player_invite", kwargs={"pk": group.pk, "player_pk": guest.pk}
    )
    assert invite_url not in content


@pytest.mark.django_db
def test_rank_detail_shows_invite_button_for_guest(client, user, group):
    client.force_login(user)
    client.post(reverse("games:create"), _load_roster_post(group))
    client.post(reverse("games:create"), _save_game_post(group))

    guest = group.players.get(display_name="Pat")
    response = client.get(
        reverse("leaderboards:detail"),
        {
            "group": str(group.pk),
            "type": "dominos",
            "player": str(guest.pk),
        },
    )
    assert response.status_code == 200
    content = response.content.decode()
    invite_url = reverse(
        "groups:player_invite", kwargs={"pk": group.pk, "player_pk": guest.pk}
    )
    assert invite_url in content
    assert "Invite" in content


@pytest.mark.django_db
def test_rank_detail_hides_invite_button_for_linked_user(client, user, group):
    client.force_login(user)
    client.post(reverse("games:create"), _load_roster_post(group))
    client.post(reverse("games:create"), _save_game_post(group))

    owner_player = group.players.get(linked_user=user)
    response = client.get(
        reverse("leaderboards:detail"),
        {
            "group": str(group.pk),
            "type": "dominos",
            "player": str(owner_player.pk),
        },
    )
    assert response.status_code == 200
    content = response.content.decode()
    invite_url = reverse(
        "groups:player_invite", kwargs={"pk": group.pk, "player_pk": owner_player.pk}
    )
    assert invite_url not in content


def _record_team_dominos(group, user):
    owner = group.players.filter(linked_user__isnull=False).first()
    nancy = add_guest_player(group=group, display_name="Nancy")
    zach = add_guest_player(group=group, display_name="Zach")
    team = resolve_side_player(group=group, members=[nancy, zach])
    record_game(
        user=user,
        group=group,
        game_type_code="dominos",
        played_on=timezone.localdate(),
        participants=[
            ParticipantInput(
                player=team,
                score=30,
                result=GameParticipantResult.Result.WIN,
                placement=0,
            ),
            ParticipantInput(
                player=owner,
                score=10,
                result=GameParticipantResult.Result.PLAYED,
                placement=1,
            ),
        ],
    )
    return owner, nancy, zach, team


@pytest.mark.django_db
def test_leaderboard_hides_player_type_filter_when_no_teams(client, user, group):
    client.force_login(user)
    client.post(reverse("games:create"), _load_roster_post(group))
    client.post(reverse("games:create"), _save_game_post(group))

    response = client.get(
        reverse("leaderboards:index"),
        {"group": str(group.pk), "type": "dominos"},
    )
    assert response.status_code == 200
    content = response.content.decode()
    assert 'name="player_type"' not in content
    assert "Users + Guests" not in content


@pytest.mark.django_db
def test_leaderboard_player_type_filter_is_players_and_teams_only(client, user, group):
    client.force_login(user)
    _record_team_dominos(group, user)

    response = client.get(
        reverse("leaderboards:index"),
        {"group": str(group.pk), "type": "dominos"},
    )
    assert response.status_code == 200
    content = response.content.decode()
    assert 'name="player_type"' in content
    assert 'value="people"' in content
    assert 'value="team"' in content
    assert "Players" in content
    assert "Teams" in content
    assert "Users + Guests" not in content
    assert (
        'value=""' not in content.split('name="player_type"')[1].split("</select>")[0]
    )
    assert 'value="user"' not in content
    assert 'value="guest"' not in content


@pytest.mark.django_db
def test_leaderboard_defaults_to_players_excluding_teams(client, user, group):
    client.force_login(user)
    owner, nancy, zach, team = _record_team_dominos(group, user)

    response = client.get(
        reverse("leaderboards:index"),
        {"group": str(group.pk), "type": "dominos"},
    )
    assert response.status_code == 200
    labels = {row.player.display_label for row in response.context["rankings"]}
    assert owner.display_label in labels
    assert nancy.display_label in labels
    assert zach.display_label in labels
    assert team.display_label not in labels


@pytest.mark.django_db
def test_leaderboard_teams_filter_shows_only_teams(client, user, group):
    client.force_login(user)
    owner, nancy, zach, team = _record_team_dominos(group, user)

    response = client.get(
        reverse("leaderboards:index"),
        {
            "group": str(group.pk),
            "type": "dominos",
            "player_type": "team",
        },
    )
    assert response.status_code == 200
    labels = {row.player.display_label for row in response.context["rankings"]}
    assert labels == {team.display_label}
    assert owner.display_label not in labels


@pytest.mark.django_db
def test_hall_of_fame_hides_player_type_filter_when_no_teams(client, user, group):
    client.force_login(user)
    client.post(reverse("games:create"), _load_roster_post(group))
    client.post(reverse("games:create"), _save_game_post(group))

    response = client.get(
        reverse("leaderboards:hall_of_fame"),
        {"group": str(group.pk)},
    )
    assert response.status_code == 200
    assert 'name="player_type"' not in response.content.decode()


@pytest.mark.django_db
def test_hall_of_fame_shows_players_teams_filter_when_teams_exist(client, user, group):
    client.force_login(user)
    _record_team_dominos(group, user)

    response = client.get(
        reverse("leaderboards:hall_of_fame"),
        {"group": str(group.pk)},
    )
    assert response.status_code == 200
    content = response.content.decode()
    assert 'name="player_type"' in content
    assert 'value="people"' in content
    assert 'value="team"' in content
    assert "Players" in content
    assert "Teams" in content
    assert "Users + Guests" not in content
