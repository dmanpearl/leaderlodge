from datetime import date

import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from leaderlodge.games.display import winner_labels_for_games
from leaderlodge.games.models import GameParticipantResult
from leaderlodge.games.services import ParticipantInput, record_game
from leaderlodge.groups.services import (
    add_group_member,
    add_guest_player,
    create_group_with_owner,
)
from leaderlodge.groups.teams import resolve_side_player
from tests.test_games import _load_roster_post, _save_game_post


@pytest.fixture
def user(db):
    return User.objects.create_user(
        username="david",
        password="test-pass-123",
        first_name="David",
        last_name="Manpearl",
    )


@pytest.fixture
def group(user):
    group = create_group_with_owner(user=user, name="Dom Club")
    add_guest_player(group=group, display_name="Pat")
    return group


@pytest.mark.django_db
def test_winner_labels_for_games(client, user, group):
    client.force_login(user)
    client.post(reverse("games:create"), _load_roster_post(group))
    client.post(reverse("games:create"), _save_game_post(group))

    game = group.games.get()
    labels = winner_labels_for_games([game])
    winner = game.participant_results.get(result=GameParticipantResult.Result.WIN)

    assert winner.player.display_label == "David M"
    assert labels[game.pk] == "David"


@pytest.mark.django_db
def test_winner_labels_drop_last_initial_without_conflict(db):
    """Dashboard Recent Games must not keep 'Nancy M' when Nancy is unique in-group."""
    david = User.objects.create_user(
        username="david",
        password="test-pass-123",
        first_name="David",
        last_name="Manpearl",
    )
    nancy = User.objects.create_user(
        username="nancy",
        password="test-pass-123",
        first_name="Nancy",
        last_name="Manpearl",
    )
    zach = User.objects.create_user(
        username="zach",
        password="test-pass-123",
        first_name="Zach",
        last_name="Quill",
    )
    manpearl = create_group_with_owner(user=david, name="manpearl")
    add_group_member(group=manpearl, user=nancy)
    add_group_member(group=manpearl, user=zach)
    test_group = create_group_with_owner(user=david, name="test")
    add_group_member(group=test_group, user=nancy)

    nancy_mp = manpearl.players.get(linked_user=nancy)
    zach_mp = manpearl.players.get(linked_user=zach)
    david_mp = manpearl.players.get(linked_user=david)
    assert nancy_mp.display_label == "Nancy M"

    team = resolve_side_player(group=manpearl, members=[nancy_mp, zach_mp])
    team.display_name = "Nancy M.+Zach Q"
    team.save(update_fields=["display_name"])

    game = record_game(
        user=david,
        group=manpearl,
        game_type_code="dominos",
        played_on=date(2026, 8, 7),
        participants=[
            ParticipantInput(
                player=team,
                score=30,
                result=GameParticipantResult.Result.WIN,
                placement=0,
            ),
            ParticipantInput(
                player=david_mp,
                score=10,
                result=GameParticipantResult.Result.PLAYED,
                placement=1,
            ),
        ],
    )

    labels = winner_labels_for_games([game])
    assert labels[game.pk] == "Nancy+Zach"
