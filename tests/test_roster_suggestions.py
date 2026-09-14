from datetime import date

import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from leaderlodge.games.roster_suggestions import (
    suggest_lineup_entries,
    suggest_side_entries,
)
from leaderlodge.games.services import ParticipantInput, record_game
from leaderlodge.groups.services import add_guest_player, create_group_with_owner
from leaderlodge.groups.teams import resolve_side_player


@pytest.fixture
def user(db):
    return User.objects.create_user(username="david", password="test-pass-123")


@pytest.fixture
def group(user):
    group = create_group_with_owner(user=user, name="Pickle Club")
    for name in ("Nancy", "Imelda", "Steve", "Melissa", "Karen"):
        add_guest_player(group=group, display_name=name)
    return group


def _players_by_name(group):
    return {player.display_name: player for player in group.players.all()}


def _record_pickleball_doubles(
    user,
    group,
    *,
    team_a,
    team_b,
    played_on,
):
    players = _players_by_name(group)
    owner = group.players.get(linked_user=user)
    side_a = resolve_side_player(
        group=group,
        members=[owner if n == "David" else players[n] for n in team_a],
    )
    side_b = resolve_side_player(
        group=group,
        members=[players[n] for n in team_b],
    )
    record_game(
        user=user,
        group=group,
        game_type_code="pickleball",
        played_on=played_on,
        participants=[
            ParticipantInput(player=side_a, score=11, result="win", placement=0),
            ParticipantInput(player=side_b, score=9, result="played", placement=1),
        ],
    )


@pytest.mark.django_db
def test_suggest_prioritizes_recent_teams_and_predicts_pairs(user, group):
    today = date(2026, 3, 15)
    _record_pickleball_doubles(
        user,
        group,
        team_a=("David", "Nancy"),
        team_b=("Imelda", "Steve"),
        played_on=today,
    )

    owner = group.players.get(linked_user=user)
    players = _players_by_name(group)
    suggestions = suggest_side_entries(group, "pickleball")
    labels = [item["label"] for item in suggestions]

    owner_label = owner.display_label
    pair_a = "+".join(sorted([owner_label, "Nancy"], key=str.lower))
    pair_b = "+".join(sorted(["Imelda", "Steve"], key=str.lower))
    assert pair_a in labels
    assert pair_b in labels


@pytest.mark.django_db
def test_suggest_excludes_players_already_in_game(user, group):
    today = date(2026, 3, 15)
    _record_pickleball_doubles(
        user,
        group,
        team_a=("David", "Nancy"),
        team_b=("Imelda", "Steve"),
        played_on=today,
    )
    players = _players_by_name(group)
    owner = group.players.get(linked_user=user)

    suggestions = suggest_side_entries(
        group,
        "pickleball",
        exclude_player_ids={owner.pk, players["Steve"].pk},
    )
    labels = [item["label"] for item in suggestions]

    owner_label = owner.display_label
    assert f"{owner_label}+Steve" not in labels and "david+Steve" not in labels
    assert "+".join(sorted([owner_label, "Nancy"], key=str.lower)) not in labels
    for item in suggestions:
        member_ids = {player["player_id"] for player in item["players"]}
        assert owner.pk not in member_ids
        assert players["Steve"].pk not in member_ids


@pytest.mark.django_db
def test_suggest_deprioritizes_teams_when_mostly_singles(user, group):
    players = _players_by_name(group)
    owner = group.players.get(linked_user=user)
    today = date(2026, 3, 15)
    for index, name in enumerate(("Nancy", "Imelda", "Melissa", "Karen")):
        record_game(
            user=user,
            group=group,
            game_type_code="pickleball",
            played_on=today,
            participants=[
                ParticipantInput(
                    player=owner if index % 2 == 0 else players[name],
                    score=11,
                    result="win",
                    placement=0,
                ),
                ParticipantInput(
                    player=players["Steve"],
                    score=9,
                    result="played",
                    placement=1,
                ),
            ],
        )

    suggestions = suggest_side_entries(group, "pickleball")
    solo_labels = [item["label"] for item in suggestions if item["kind"] == "solo"]
    team_labels = [item["label"] for item in suggestions if item["kind"] == "team"]

    assert solo_labels
    if team_labels:
        first_team = suggestions.index(
            next(item for item in suggestions if item["kind"] == "team")
        )
        first_solo = suggestions.index(
            next(item for item in suggestions if item["kind"] == "solo")
        )
        assert first_solo <= first_team


@pytest.mark.django_db
def test_suggest_filters_by_query(user, group):
    today = date(2026, 3, 15)
    _record_pickleball_doubles(
        user,
        group,
        team_a=("David", "Nancy"),
        team_b=("Imelda", "Steve"),
        played_on=today,
    )

    suggestions = suggest_side_entries(group, "pickleball", query="nan")
    labels = [item["label"].lower() for item in suggestions]

    assert any("nancy" in label for label in labels)
    assert not any("steve" in label for label in labels)


@pytest.mark.django_db
def test_suggest_teammate_mode_returns_solo_only(user, group):
    today = date(2026, 3, 15)
    _record_pickleball_doubles(
        user,
        group,
        team_a=("David", "Nancy"),
        team_b=("Imelda", "Steve"),
        played_on=today,
    )

    suggestions = suggest_side_entries(group, "pickleball", teammate_mode=True)

    assert suggestions
    assert all(item["kind"] == "solo" for item in suggestions)


@pytest.mark.django_db
def test_suggest_lineup_replays_recent_matchup(user, group):
    today = date(2026, 3, 15)
    _record_pickleball_doubles(
        user,
        group,
        team_a=("David", "Nancy"),
        team_b=("Imelda", "Steve"),
        played_on=today,
    )

    owner = group.players.get(linked_user=user)
    players = _players_by_name(group)
    lineups = suggest_lineup_entries(group, "pickleball")

    assert lineups
    first = lineups[0]
    assert first["source"] == "replay"
    assert len(first["sides"]) == 2
    assert first["summary"]
    owner_label = owner.display_label
    pair_a = "+".join(sorted([owner_label, "Nancy"], key=str.lower))
    pair_b = "+".join(sorted(["Imelda", "Steve"], key=str.lower))
    assert pair_a in first["summary"]
    assert pair_b in first["summary"]
    member_ids = {
        player["player_id"] for side in first["sides"] for player in side["players"]
    }
    assert owner.pk in member_ids
    assert players["Nancy"].pk in member_ids
    assert players["Imelda"].pk in member_ids
    assert players["Steve"].pk in member_ids


@pytest.mark.django_db
def test_suggest_lineup_endpoint_returns_full_sides(client, user, group):
    today = date(2026, 3, 15)
    _record_pickleball_doubles(
        user,
        group,
        team_a=("David", "Nancy"),
        team_b=("Imelda", "Steve"),
        played_on=today,
    )
    client.force_login(user)
    response = client.get(
        reverse("games:suggest_sides"),
        {"group": str(group.pk), "type": "pickleball", "lineup": "1"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["suggestions"]
    assert payload["suggestions"][0]["sides"]
    assert len(payload["suggestions"][0]["sides"]) >= 2


@pytest.mark.django_db
def test_record_game_shows_reuse_suggest_segmented_buttons(client, user, group):
    today = date(2026, 3, 15)
    _record_pickleball_doubles(
        user,
        group,
        team_a=("David", "Nancy"),
        team_b=("Imelda", "Steve"),
        played_on=today,
    )
    client.force_login(user)
    response = client.get(
        reverse("games:create"),
        {"group": str(group.pk), "game_type_code": "pickleball"},
    )
    assert response.status_code == 200
    content = response.content.decode()
    assert 'role="group"' in content
    assert "game-record-lineup-actions" in content
    assert 'id="reuse-players-btn"' in content
    assert 'id="suggest-sides-btn"' in content
    assert "Suggest" in content
    assert reverse("games:suggest_sides") in content
    assert "game_setup_suggest.js" in content


@pytest.mark.django_db
def test_suggest_sides_endpoint(client, user, group):
    today = date(2026, 3, 15)
    _record_pickleball_doubles(
        user,
        group,
        team_a=("David", "Nancy"),
        team_b=("Imelda", "Steve"),
        played_on=today,
    )
    client.force_login(user)
    response = client.get(
        reverse("games:suggest_sides"),
        {"group": str(group.pk), "type": "pickleball"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["suggestions"]
    assert payload["suggestions"][0]["players"]
