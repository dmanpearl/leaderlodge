import pytest

from leaderlodge.games.scoring import assign_results_from_scores
from leaderlodge.games.services import ParticipantInput, record_game
from leaderlodge.groups.services import add_guest_player, create_group_with_owner
from leaderlodge.insights.tools.executor import AskScope, ToolExecutor
from leaderlodge.insights.tools.placements import query_placement_leaders
from leaderlodge.leaderboards.period import LeaderboardPeriod


@pytest.fixture
def user(db):
    from django.contrib.auth.models import User

    return User.objects.create_user(username="david", password="test-pass-123")


@pytest.fixture
def group(user):
    group = create_group_with_owner(user=user, name="Dom Club")
    add_guest_player(group=group, display_name="Pat")
    add_guest_player(group=group, display_name="Sam")
    return group


def _record_game(group, user, *, winner_idx=0, loser_idx=1, third_idx=2):
    players = list(group.players.order_by("pk"))
    rows = [
        {"player": players[winner_idx], "score": 35},
        {"player": players[loser_idx], "score": 20},
    ]
    if third_idx is not None and len(players) > 2:
        rows.append({"player": players[third_idx], "score": 15})
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
        played_on="2026-01-15",
        participants=participants,
    )


@pytest.mark.django_db
def test_query_placement_leaders_returns_second_place_counts(user, group):
    add_guest_player(group=group, display_name="Alex")
    _record_game(group, user, winner_idx=0, loser_idx=1, third_idx=2)
    _record_game(group, user, winner_idx=1, loser_idx=0, third_idx=2)

    result = query_placement_leaders(
        group,
        game_type_code="dominos",
        placement=1,
    )

    assert result["placement_label"] == "2nd"
    assert len(result["leaders"]) >= 1
    top = result["leaders"][0]
    assert top["weighted_count"] >= 1


@pytest.mark.django_db
def test_query_head_to_head_counts_shared_games(user, group):
    _record_game(group, user, winner_idx=0, loser_idx=1, third_idx=2)
    _record_game(group, user, winner_idx=1, loser_idx=0, third_idx=2)
    players = list(group.players.order_by("pk"))

    from leaderlodge.insights.tools.head_to_head import query_head_to_head

    result = query_head_to_head(
        group,
        game_type_code="dominos",
        player_a_id=players[0].pk,
        player_b_id=players[1].pk,
    )

    assert result["games_together"] == 2
    assert result["player_a"]["games_played"] == 2
    assert result["player_b"]["games_played"] == 2
    assert result["player_a"]["wins"] + result["player_b"]["wins"] == 2


@pytest.mark.django_db
def test_query_hall_of_fame_returns_period_leaders(user, group):
    _record_game(group, user, third_idx=None)
    from leaderlodge.insights.tools.hall_of_fame import query_hall_of_fame

    result = query_hall_of_fame(group, granularity="year", game_type_code="dominos")

    assert result["granularity"] == "year"
    assert len(result["periods"]) >= 1
    leaders = result["periods"][0]["leaders"]
    assert len(leaders) == 1
    assert leaders[0]["leader"]


@pytest.mark.django_db
def test_tool_executor_query_head_to_head(user, group):
    _record_game(group, user, third_idx=None)
    scope = AskScope(
        group=group,
        period=LeaderboardPeriod.all_time(),
        default_game_type_code="dominos",
        available_game_type_codes=("dominos",),
    )
    executor = ToolExecutor(scope)
    players = list(group.players.order_by("pk"))

    result = executor.execute(
        "query_head_to_head",
        {
            "game_type_code": "dominos",
            "player_a_query": players[0].display_label,
            "player_b_query": players[1].display_label,
        },
    )

    assert result["games_together"] == 1


@pytest.mark.django_db
def test_tool_executor_all_time_overrides_scope_period(user, group):
    _record_game(group, user, third_idx=None)
    scope = AskScope(
        group=group,
        period=LeaderboardPeriod(year=2020),
        default_game_type_code="dominos",
        available_game_type_codes=("dominos",),
    )
    executor = ToolExecutor(scope)

    result = executor.execute(
        "query_leaderboard",
        {"game_type_code": "dominos", "all_time": True},
    )

    assert result["period"] == {"all_time": True}


@pytest.mark.django_db
def test_query_player_detail_includes_score_highlights(user, group):
    _record_game(group, user, third_idx=None)
    player = group.players.order_by("pk").first()
    from leaderlodge.insights.tools.standings import query_player_detail

    result = query_player_detail(
        group,
        player_id=player.pk,
        game_type_code="dominos",
    )

    assert result["best_score"] is not None
    assert result["podium_count"] >= 0
    assert result["date_range_label"]


@pytest.mark.django_db
def test_tool_executor_rejects_unknown_game_type(user, group):
    _record_game(group, user, third_idx=None)
    scope = AskScope(
        group=group,
        period=LeaderboardPeriod.all_time(),
        default_game_type_code="dominos",
        available_game_type_codes=("dominos",),
    )
    executor = ToolExecutor(scope)

    with pytest.raises(Exception, match="Game type not found"):
        executor.execute(
            "query_leaderboard",
            {"game_type_code": "mahjongg"},
        )
