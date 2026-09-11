import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from leaderlodge.games.models import GameParticipantResult
from leaderlodge.games.services import ParticipantInput, record_game
from leaderlodge.groups.player_search import (
    DEFAULT_RECENCY,
    recency_ranks_for_group,
    resolve_participant_player,
    resolve_typed_player_name,
    roster_for_group,
    search_group_players,
)
from leaderlodge.groups.services import add_guest_player, create_group_with_owner
from leaderlodge.groups.teams import resolve_side_player


@pytest.fixture
def user(db):
    return User.objects.create_user(username="david", password="test-pass-123")


@pytest.fixture
def group(user):
    group = create_group_with_owner(user=user, name="Dom Club")
    add_guest_player(group=group, display_name="Pat")
    return group


def _people(group):
    owner = group.players.filter(linked_user__isnull=False).first()
    nancy = add_guest_player(group=group, display_name="Nancy")
    zach = add_guest_player(group=group, display_name="Zach")
    sally = add_guest_player(group=group, display_name="Sally")
    return owner, nancy, zach, sally


@pytest.mark.django_db
def test_search_group_players_matches_username(group, user):
    results = search_group_players(group, "david")
    assert any(entry["username"] == "david" for entry in results)


@pytest.mark.django_db
def test_resolve_typed_player_name_matches_linked_username(group, user):
    owner = group.players.filter(linked_user__isnull=False).first()
    assert resolve_typed_player_name(group=group, name="david") == owner


@pytest.mark.django_db
def test_resolve_participant_player_matches_username_without_player_id(group, user):
    owner = group.players.filter(linked_user__isnull=False).first()
    resolved = resolve_participant_player(
        group=group, player_id=None, guest_name="david"
    )
    assert resolved == owner
    assert resolved.linked_user_id == user.pk


@pytest.mark.django_db
def test_resolve_participant_player_matches_disambiguated_label(group, user):
    owner = group.players.filter(linked_user__isnull=False).first()
    resolved = resolve_participant_player(
        group=group, player_id=None, guest_name=owner.display_label
    )
    assert resolved == owner


@pytest.mark.django_db
def test_roster_for_group_includes_teams(group, user):
    _, nancy, zach, _ = _people(group)
    resolve_side_player(group=group, members=[nancy, zach])

    roster = roster_for_group(group)
    team_entries = [entry for entry in roster if entry["kind"] == "team"]

    assert any(entry["label"] == "Nancy+Zach" for entry in team_entries)
    team_entry = next(entry for entry in team_entries if entry["label"] == "Nancy+Zach")
    assert len(team_entry["members"]) == 2
    assert {member["label"] for member in team_entry["members"]} == {"Nancy", "Zach"}
    assert "recency" in team_entry


@pytest.mark.django_db
def test_recency_ranks_use_most_recent_game(group, user):
    owner, nancy, zach, _ = _people(group)
    team = resolve_side_player(group=group, members=[nancy, zach])

    record_game(
        user=user,
        group=group,
        game_type_code="dominos",
        played_on="2026-01-01",
        participants=[
            ParticipantInput(
                player=nancy,
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
    record_game(
        user=user,
        group=group,
        game_type_code="dominos",
        played_on="2026-02-01",
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

    ranks = recency_ranks_for_group(group)
    assert ranks[team.pk] < ranks[nancy.pk]


@pytest.mark.django_db
def test_search_group_players_orders_teams_by_recency(group, user):
    owner, nancy, zach, sally = _people(group)
    team_nz = resolve_side_player(group=group, members=[nancy, zach])
    team_ns = resolve_side_player(group=group, members=[nancy, sally])

    record_game(
        user=user,
        group=group,
        game_type_code="dominos",
        played_on="2026-01-01",
        participants=[
            ParticipantInput(
                player=team_ns,
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
    record_game(
        user=user,
        group=group,
        game_type_code="dominos",
        played_on="2026-02-01",
        participants=[
            ParticipantInput(
                player=team_nz,
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

    results = search_group_players(group, "nancy")
    team_labels = [entry["label"] for entry in results if entry["kind"] == "team"]

    assert team_labels.index("Nancy+Zach") < team_labels.index("Nancy+Sally")


@pytest.mark.django_db
def test_search_group_players_finds_team_by_member_name(group, user):
    _, nancy, zach, _ = _people(group)
    resolve_side_player(group=group, members=[nancy, zach])

    results = search_group_players(group, "zach")
    assert any(
        entry["kind"] == "team" and entry["label"] == "Nancy+Zach" for entry in results
    )


@pytest.mark.django_db
def test_roster_marks_never_played_with_default_recency(group, user):
    _, nancy, _, _ = _people(group)

    roster = roster_for_group(group)
    nancy_entry = next(entry for entry in roster if entry["label"] == "Nancy")

    assert nancy_entry["recency"] == DEFAULT_RECENCY


@pytest.mark.django_db
def test_roster_deprioritizes_team_with_no_history_in_game_type(group, user):
    owner, nancy, zach, _ = _people(group)
    team = resolve_side_player(group=group, members=[nancy, zach])

    record_game(
        user=user,
        group=group,
        game_type_code="pickleball",
        played_on="2026-02-01",
        participants=[
            ParticipantInput(
                player=team,
                score=11,
                result=GameParticipantResult.Result.WIN,
                placement=0,
            ),
            ParticipantInput(
                player=owner,
                score=5,
                result=GameParticipantResult.Result.PLAYED,
                placement=1,
            ),
        ],
    )

    roster = roster_for_group(group, game_type_code="mahjongg")
    team_entry = next(entry for entry in roster if entry["label"] == "Nancy+Zach")

    assert team_entry["deprioritized"] is True
    assert team_entry["recency"] == DEFAULT_RECENCY

    # Without game_type_code scoping, no team is deprioritized.
    unscoped_roster = roster_for_group(group)
    unscoped_team_entry = next(
        entry for entry in unscoped_roster if entry["label"] == "Nancy+Zach"
    )
    assert unscoped_team_entry["deprioritized"] is False


@pytest.mark.django_db
def test_roster_keeps_team_recency_when_used_for_game_type(group, user):
    owner, nancy, zach, _ = _people(group)
    team = resolve_side_player(group=group, members=[nancy, zach])

    record_game(
        user=user,
        group=group,
        game_type_code="pickleball",
        played_on="2026-03-01",
        participants=[
            ParticipantInput(
                player=team,
                score=11,
                result=GameParticipantResult.Result.WIN,
                placement=0,
            ),
            ParticipantInput(
                player=owner,
                score=5,
                result=GameParticipantResult.Result.PLAYED,
                placement=1,
            ),
        ],
    )
    record_game(
        user=user,
        group=group,
        game_type_code="pickleball",
        played_on="2026-01-01",
        participants=[
            ParticipantInput(
                player=nancy,
                score=11,
                result=GameParticipantResult.Result.WIN,
                placement=0,
            ),
            ParticipantInput(
                player=owner,
                score=5,
                result=GameParticipantResult.Result.PLAYED,
                placement=1,
            ),
        ],
    )

    roster = roster_for_group(group, game_type_code="pickleball")
    team_entry = next(entry for entry in roster if entry["label"] == "Nancy+Zach")
    nancy_entry = next(
        entry
        for entry in roster
        if entry["label"] == "Nancy" and entry["kind"] != "team"
    )

    assert team_entry["deprioritized"] is False
    assert team_entry["recency"] < nancy_entry["recency"]


@pytest.mark.django_db
def test_search_group_players_puts_deprioritized_teams_after_matching_individuals(
    group, user
):
    owner, nancy, zach, sally = _people(group)
    team = resolve_side_player(group=group, members=[nancy, zach])

    record_game(
        user=user,
        group=group,
        game_type_code="pickleball",
        played_on="2026-02-01",
        participants=[
            ParticipantInput(
                player=team,
                score=11,
                result=GameParticipantResult.Result.WIN,
                placement=0,
            ),
            ParticipantInput(
                player=owner,
                score=5,
                result=GameParticipantResult.Result.PLAYED,
                placement=1,
            ),
        ],
    )

    results = search_group_players(group, "an", game_type_code="mahjongg")
    labels = [entry["label"] for entry in results]

    # "Nancy" (individual) matches "an" and has no game-type history baggage;
    # the pickleball-only "Nancy+Zach" team must not outrank it just because
    # the team happens to have recent (pickleball) history.
    assert "Nancy" in labels
    team_index = labels.index("Nancy+Zach") if "Nancy+Zach" in labels else None
    nancy_index = labels.index("Nancy")
    if team_index is not None:
        assert nancy_index < team_index


from tests.test_games import _load_roster_post


@pytest.mark.django_db
def test_game_create_roster_json_includes_teams(client, user, group):
    _, nancy, zach, _ = _people(group)
    team = resolve_side_player(group=group, members=[nancy, zach])

    client.force_login(user)
    response = client.post(
        reverse("games:create"),
        _load_roster_post(group, game_type_code="dominos"),
    )

    assert response.status_code == 200
    content = response.content.decode()
    assert '"kind": "team"' in content
    assert "Nancy+Zach" in content
    import json
    import re

    match = re.search(
        r'<script id="game-roster-data" type="application/json">(.*?)</script>',
        content,
        re.S,
    )
    assert match is not None
    roster = json.loads(match.group(1))
    team_entry = next(entry for entry in roster if entry["kind"] == "team")
    assert len(team_entry["members"]) == 2
    assert {member["label"] for member in team_entry["members"]} == {"Nancy", "Zach"}


@pytest.mark.django_db
def test_group_players_search_hidden_from_non_member(client, group):
    other = User.objects.create_user(username="alice", password="test-pass-123")
    client.force_login(other)
    response = client.get(
        reverse("groups:players_search", kwargs={"pk": group.pk}),
        {"q": "pat"},
    )

    assert response.status_code == 404
