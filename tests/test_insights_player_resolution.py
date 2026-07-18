import pytest
from django.contrib.auth.models import User

from leaderlodge.groups.services import add_guest_player, create_group_with_owner
from leaderlodge.insights.tools.executor import AskScope, ToolExecutor
from leaderlodge.insights.tools.players import (
    build_ask_player_roster,
    build_question_player_hints,
    resolve_player_query,
)
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
    add_guest_player(group=group, display_name="Charlene")
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
def test_resolve_player_query_does_not_match_shared_username_suffix(group):
    nancy = group.players.get(linked_user__username="nmanpearl")
    with pytest.raises(ValueError, match="No player matched"):
        resolve_player_query(group, "manpearl")
    assert resolve_player_query(group, "nmanpearl").pk == nancy.pk


@pytest.mark.django_db
def test_build_question_player_hints_for_username_comparison(group):
    hints = build_question_player_hints(group, "nmanpearl vs charlene")

    assert hints is not None
    assert "Nancy: player_id=" in hints
    assert "question text: nmanpearl" in hints
    assert "Charlene: player_id=" in hints


@pytest.mark.django_db
def test_resolve_player_query_accepts_quoted_username(group):
    nancy = group.players.get(linked_user__username="nmanpearl")

    assert resolve_player_query(group, '"nmanpearl"').pk == nancy.pk


@pytest.mark.django_db
def test_tool_executor_uses_question_player_bindings(group):
    from leaderlodge.insights.tools.players import (
        question_player_binding_map,
        resolve_question_player_bindings,
    )

    bindings = resolve_question_player_bindings(group, "nmanpearl vs charlene")
    scope = AskScope(
        group=group,
        period=LeaderboardPeriod.all_time(),
        default_game_type_code="dominos",
        available_game_type_codes=("dominos",),
        question_player_bindings=question_player_binding_map(bindings),
    )
    executor = ToolExecutor(scope)
    nancy = group.players.get(linked_user__username="nmanpearl")

    player_id = executor._resolve_player_id_from_args(
        {"player_a_query": '"nmanpearl"'},
        prefix="player_a_",
    )

    assert player_id == nancy.pk


@pytest.mark.django_db
def test_leader_question_does_not_bind_short_name_inside_word(group):
    add_guest_player(group=group, display_name="Bo")

    hints = build_question_player_hints(group, "Tell me about the leader")

    assert hints is None


@pytest.mark.django_db
def test_resolve_player_query_leader_is_not_a_player_name(group):
    add_guest_player(group=group, display_name="Bo")

    with pytest.raises(ValueError, match="Use query_leaderboard"):
        resolve_player_query(group, "leader")
