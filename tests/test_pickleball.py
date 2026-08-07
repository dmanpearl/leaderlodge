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
    players = list(group.players.order_by("pk"))
    save_response = client.post(
        reverse("games:create"),
        _save_pickleball_post(
            group,
            score_type="rally",
            scores={players[0].pk: 11, players[1].pk: 7},
        ),
    )
    assert save_response.status_code == 302
    from leaderlodge.games.models import Game
    assert Game.objects.filter(group=group, game_type_code="pickleball").exists()

    response = client.get(
        reverse("games:list"),
        {"group": str(group.pk), "type": "pickleball"},
        follow=True,
    )
    content = response.content.decode()
    assert "game-list-table" in content, content[content.find("card"):content.find("card")+400]
    games_table = content.split("game-list-table ", 1)[1].split("</table>", 1)[0]

    assert response.status_code == 200
    assert "game-types/pickleball.png" in games_table
    assert ">R</span>" in games_table
    assert games_table.count("game-list-weight-badge") == 1


@pytest.mark.django_db
def test_pickleball_rank_score_ignores_winning_score_margin(user, group):
    from leaderlodge.games.scoring import assign_results_from_scores
    from leaderlodge.games.services import ParticipantInput, record_game
    from leaderlodge.leaderboards.service import get_player_rankings

    players = list(group.players.order_by("pk"))
    add_guest_player(group=group, display_name="Sam")

    def record_win(*, winner_idx, winner_score, loser_score):
        rows = [
            {"player": players[winner_idx], "score": winner_score},
            {"player": players[1 - winner_idx], "score": loser_score},
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

    record_win(winner_idx=0, winner_score=11, loser_score=3)
    record_win(winner_idx=0, winner_score=15, loser_score=12)

    winner = get_player_rankings(group, game_type_code="pickleball")[0]
    assert winner.player.pk == players[0].pk
    assert winner.finish_points == pytest.approx(4.0)
    assert winner.games_played == pytest.approx(2.0)


@pytest.mark.django_db
def test_undefeated_team_is_not_buried_by_bayesian_shrinkage(user, group):
    from leaderlodge.games.scoring import assign_results_from_scores
    from leaderlodge.games.services import ParticipantInput, record_game
    from leaderlodge.groups.teams import resolve_side_player
    from leaderlodge.leaderboards.service import get_player_rankings

    owner = group.players.get(linked_user=user)
    sara = add_guest_player(group=group, display_name="Sara")
    opponent = add_guest_player(group=group, display_name="Opponent")
    team = resolve_side_player(group=group, members=[owner, sara])

    for _ in range(3):
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

    team_row = get_player_rankings(
        group, game_type_code="pickleball", player_type="team"
    )[0]
    assert team_row.player.pk == team.pk
    assert team_row.games_played == pytest.approx(3.0)
    # Team-context shrinkage (LEADERBOARD_TEAM_BAYESIAN_K) keeps a clean 3-0
    # pair competitive instead of collapsing it toward zero the way the
    # individual-context LEADERBOARD_BAYESIAN_K (k=20) would.
    assert team_row.rank_score > 0.5
