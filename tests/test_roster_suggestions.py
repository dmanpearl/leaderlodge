from datetime import date

import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from leaderlodge.games.roster_suggestions import suggest_side_entries
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
