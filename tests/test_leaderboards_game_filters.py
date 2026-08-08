import pytest
from datetime import date
from django.contrib.auth.models import User
from django.urls import reverse

from leaderlodge.games.registry import ScoreType
from leaderlodge.games.scoring import assign_results_from_scores
from leaderlodge.games.services import ParticipantInput, record_game
from leaderlodge.groups.services import add_guest_player, create_group_with_owner
from leaderlodge.leaderboards.game_filters import (
    LeaderboardGameFilters,
    apply_game_filters_to_results_qs,
    game_filter_context,
    resolve_leaderboard_game_filters,
)
from leaderlodge.leaderboards.service import get_player_rankings
from tests.test_games import _load_roster_post, _save_game_post
from tests.test_pickleball import _save_pickleball_post


@pytest.fixture
def user(db):
    return User.objects.create_user(username="david", password="test-pass-123")


@pytest.fixture
def group(user):
    group = create_group_with_owner(user=user, name="Filter Club")
    add_guest_player(group=group, display_name="Pat")
    add_guest_player(group=group, display_name="Sam")
    return group


def test_resolve_leaderboard_game_filters_ignores_irrelevant_params():
    filters = resolve_leaderboard_game_filters(
        {"score_type": "rally", "double_game": "1", "half_game": "1"},
        game_type_code="dominos",
    )
    assert filters == LeaderboardGameFilters(double_game=True)


def test_game_filter_context_only_shows_supported_fields():
    ctx = game_filter_context(
        game_type_code="pickleball",
        selected_filters=LeaderboardGameFilters(score_type="rally"),
    )
    assert len(ctx["game_feature_filters"]) == 1
    assert ctx["game_feature_filters"][0]["key"] == "score_type"
    assert ctx["game_feature_filters"][0]["selected"] == "rally"
    assert ctx["game_filter_labels"] == ["Rally"]

    ctx = game_filter_context(
        game_type_code="progressiverummy",
        selected_filters=LeaderboardGameFilters(half_game=True),
    )
    assert len(ctx["game_feature_filters"]) == 1
    assert ctx["game_feature_filters"][0]["key"] == "half_game"
    assert ctx["game_feature_filters"][0]["selected"] == "1"
    assert ctx["game_feature_filters"][0]["title"] == "Game length"


@pytest.mark.django_db
def test_get_player_rankings_filters_by_score_type(client, user, group):
    client.force_login(user)
    players = list(group.players.order_by("pk"))
    client.post(
        reverse("games:create"),
        _load_roster_post(group, game_type_code="pickleball"),
    )
    client.post(
        reverse("games:create"),
        _save_pickleball_post(
            group,
            score_type="traditional",
            scores={players[0].pk: 11, players[1].pk: 7},
        ),
    )
    client.post(
        reverse("games:create"),
        _load_roster_post(group, game_type_code="pickleball"),
    )
    client.post(
        reverse("games:create"),
        _save_pickleball_post(
            group,
            score_type="rally",
            scores={players[0].pk: 11, players[1].pk: 9},
        ),
    )

    all_types = get_player_rankings(group, game_type_code="pickleball")
    rally_only = get_player_rankings(
        group,
        game_type_code="pickleball",
        game_filters=LeaderboardGameFilters(score_type=ScoreType.RALLY.value),
    )

    winner_all = next(row for row in all_types if row.wins > 0)
    winner_rally = next(row for row in rally_only if row.wins > 0)
    assert winner_all.games_played == 2
    assert winner_rally.games_played == 1


@pytest.mark.django_db
def test_get_player_rankings_filters_by_double_game(client, user, group):
    client.force_login(user)
    players = list(group.players.order_by("pk"))
    client.post(reverse("games:create"), _load_roster_post(group))
    client.post(
        reverse("games:create"),
        _save_game_post(
            group,
            players_played=players[:2],
            scores={players[0].pk: 30, players[1].pk: 20},
        ),
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

    all_games = get_player_rankings(group, game_type_code="dominos")
    double_only = get_player_rankings(
        group,
        game_type_code="dominos",
        game_filters=LeaderboardGameFilters(double_game=True),
    )
    regular_only = get_player_rankings(
        group,
        game_type_code="dominos",
        game_filters=LeaderboardGameFilters(double_game=False),
    )

    winner_all = next(row for row in all_games if row.wins > 0)
    winner_double = next(row for row in double_only if row.wins > 0)
    winner_regular = next(row for row in regular_only if row.wins > 0)
    assert winner_all.games_played == 3
    assert winner_double.games_played == 2
    assert winner_regular.games_played == 1


@pytest.mark.django_db
def test_get_player_rankings_filters_by_half_game(user, group):
    players = list(group.players.order_by("pk"))
    add_guest_player(group=group, display_name="Alex")
    players = list(group.players.order_by("pk"))
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
    record_game(
        user=user,
        group=group,
        game_type_code="progressiverummy",
        played_on=date(2026, 1, 2),
        participants=participants,
        half_weight=1,
    )

    all_games = get_player_rankings(group, game_type_code="progressiverummy")
    half_only = get_player_rankings(
        group,
        game_type_code="progressiverummy",
        game_filters=LeaderboardGameFilters(half_game=True),
    )

    winner_all = next(row for row in all_games if row.wins > 0)
    winner_half = next(row for row in half_only if row.wins > 0)
    assert winner_all.games_played == 1.5
    assert winner_half.games_played == 0.5


@pytest.mark.django_db
def test_leaderboard_view_shows_game_option_filters_by_type(client, user, group):
    client.force_login(user)
    players = list(group.players.order_by("pk"))
    client.post(reverse("games:create"), _load_roster_post(group))
    client.post(reverse("games:create"), _save_game_post(group))
    client.post(
        reverse("games:create"),
        _load_roster_post(group, game_type_code="pickleball"),
    )
    client.post(
        reverse("games:create"),
        _save_pickleball_post(group, score_type="rally"),
    )

    dominos_response = client.get(
        reverse("leaderboards:index"),
        {"group": str(group.pk), "type": "dominos"},
    )
    dominos_content = dominos_response.content.decode()
    assert dominos_response.status_code == 200
    assert 'name="double_game"' in dominos_content
    assert 'name="score_type"' not in dominos_content
    assert 'name="half_game"' not in dominos_content

    pickleball_response = client.get(
        reverse("leaderboards:index"),
        {"group": str(group.pk), "type": "pickleball"},
    )
    pickleball_content = pickleball_response.content.decode()
    assert pickleball_response.status_code == 200
    assert 'name="score_type"' in pickleball_content
    assert 'name="double_game"' not in pickleball_content
    assert 'name="half_game"' not in pickleball_content
    assert (
        ">Score type<" in pickleball_content
        or "Score type</label>" in pickleball_content
    )


@pytest.mark.django_db
def test_leaderboard_view_shows_mahjongg_style_filter_with_icon(client, user, group):
    client.force_login(user)
    response = client.get(
        reverse("leaderboards:index"),
        {"group": str(group.pk), "type": "mahjongg", "score_type": "japanese"},
    )
    assert response.status_code == 200
    content = response.content.decode()
    assert 'name="score_type"' in content
    assert "Style" in content
    assert "mj-japan.png" in content
    assert 'value="japanese"' in content


@pytest.mark.django_db
def test_apply_game_filters_to_results_qs(user, group):
    from leaderlodge.games.models import Game, GameParticipantResult

    players = list(group.players.order_by("pk"))
    rows = [
        {"player": players[0], "score": 77},
        {"player": players[1], "score": 76},
    ]
    assign_results_from_scores(rows, "dominos")
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
        game_type_code="dominos",
        played_on=date(2026, 1, 1),
        participants=participants,
    )
    qs = GameParticipantResult.objects.filter(game__group=group)
    filtered = apply_game_filters_to_results_qs(
        qs,
        LeaderboardGameFilters(double_game=True),
        game_type_code="dominos",
    )
    assert filtered.count() == 2
    assert all(result.game.double_weight == 2 for result in filtered)
    assert Game.objects.filter(group=group).count() == 1
