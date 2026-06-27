import pytest
from django.contrib.auth.models import User

from leaderlodge.groups.services import add_guest_player, create_group_with_owner
from leaderlodge.insights.tools.executor import AskScope, ToolExecutor
from leaderlodge.insights.tools.players import build_ask_player_roster, resolve_player_query
from leaderlodge.leaderboards.period import LeaderboardPeriod


@pytest.fixture
def group(db):
    nancy = User.objects.create_user(
        username="nmanpearl",
        password="test-pass-123",
        first_name="Nancy",
    )
    david = User.objects.create_user(
        username="dmanpearl",
        password="test-pass-123",
        first_name="David",
    )
    group = create_group_with_owner(user=nancy, name="Dom Club")
    group.players.filter(linked_user=nancy).update(display_name="Nancy P.")
    david_player = add_guest_player(group=group, display_name="David Guest")
    david_player.linked_user = david
    david_player.save(update_fields=["linked_user"])
    return group


@pytest.mark.django_db
def test_build_ask_player_roster_includes_name_aliases(group):
    roster = build_ask_player_roster(group)
    by_username = {row["username"]: row for row in roster if "username" in row}

    assert by_username["nmanpearl"]["display_label"] == "Nancy"
    assert by_username["nmanpearl"]["first_name"] == "Nancy"
    assert by_username["dmanpearl"]["display_label"] == "David"


@pytest.mark.django_db
def test_resolve_player_query_matches_first_name_and_username(group):
    nancy = group.players.get(linked_user__username="nmanpearl")
    david = group.players.get(linked_user__username="dmanpearl")

    assert resolve_player_query(group, "Nancy").pk == nancy.pk
    assert resolve_player_query(group, "David").pk == david.pk
    assert resolve_player_query(group, "nmanpearl").pk == nancy.pk
    assert resolve_player_query(group, "dmanpearl").pk == david.pk


@pytest.mark.django_db
def test_query_player_detail_accepts_player_query(group):
    scope = AskScope(
        group=group,
        period=LeaderboardPeriod.all_time(),
        default_game_type_code="dominos",
        available_game_type_codes=("dominos",),
    )
    executor = ToolExecutor(scope)

    result = executor.execute(
        "query_player_detail",
        {"player_query": "Nancy", "game_type_code": "dominos"},
    )

    assert result["display_label"] == "Nancy"
    assert result["has_games"] is False
