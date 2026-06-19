import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from leaderlodge.games.display import winner_labels_for_games
from leaderlodge.games.models import GameParticipantResult
from leaderlodge.groups.services import add_guest_player, create_group_with_owner
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
def test_winner_labels_for_games(client, user, group):
    client.force_login(user)
    client.post(reverse("games:create"), _load_roster_post(group))
    client.post(reverse("games:create"), _save_game_post(group))

    game = group.games.get()
    labels = winner_labels_for_games([game])
    winner = game.participant_results.get(result=GameParticipantResult.Result.WIN)

    assert labels[game.pk] == winner.player.display_label
