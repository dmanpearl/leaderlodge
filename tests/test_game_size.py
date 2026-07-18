import pytest

from leaderlodge.games.game_size import (
    available_game_sizes,
)
from leaderlodge.games.models import Game
from leaderlodge.groups.services import add_guest_player, create_group_with_owner


@pytest.fixture
def user(db):
    from django.contrib.auth.models import User

    return User.objects.create_user(username="david", password="test-pass-123")


@pytest.fixture
def group(user):
    group = create_group_with_owner(user=user, name="Dom Club")
    add_guest_player(group=group, display_name="Pat")
    return group


@pytest.mark.django_db
def test_available_game_sizes_returns_sorted_unique_counts(user, group):
    Game.objects.create(
        group=group,
        game_type_code="dominos",
        played_on="2026-01-01",
        recorded_by=user,
        player_count=2,
    )
    Game.objects.create(
        group=group,
        game_type_code="dominos",
        played_on="2026-01-02",
        recorded_by=user,
        player_count=3,
    )
    Game.objects.create(
        group=group,
        game_type_code="dominos",
        played_on="2026-01-03",
        recorded_by=user,
        player_count=2,
    )

    assert available_game_sizes(Game.objects.filter(group=group)) == (2, 3)


