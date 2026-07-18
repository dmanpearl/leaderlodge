import pytest
from django.contrib.auth.models import User
from django.urls import reverse

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
def test_dashboard_welcome_uses_display_name(client, user, group):
    user.first_name = "David"
    user.save(update_fields=["first_name"])
    client.force_login(user)
    content = client.get(reverse("core:dashboard")).content.decode()
    assert "Welcome, David." in content
    assert "Welcome, david." not in content
    assert 'class="page-header-logo"' in content
    assert "dashboard-header--mobile" in content
    assert "dashboard-mobile-welcome" in content
    assert ">Dashboard</span>" in content


@pytest.mark.django_db
def test_dashboard_recent_game_rows_link_to_detail(client, user, group):
    client.force_login(user)
    client.post(reverse("games:create"), _load_roster_post(group))
    client.post(reverse("games:create"), _save_game_post(group))

    game = group.games.get()
    detail_url = reverse("games:detail", kwargs={"pk": game.pk})
    content = client.get(reverse("core:dashboard")).content.decode()

    assert 'class="dashboard-recent-game-row"' in content
    assert f'data-href="{detail_url}"' in content
    assert f'<a href="{detail_url}">' not in content


@pytest.mark.django_db
def test_dashboard_composite_leaderboards(client, user, group):
    other_group = create_group_with_owner(user=user, name="Other Club")
    add_guest_player(group=other_group, display_name="Pat")

    client.force_login(user)
    client.post(reverse("games:create"), _load_roster_post(group))
    client.post(reverse("games:create"), _save_game_post(group))
    client.post(reverse("games:create"), _load_roster_post(other_group))
    client.post(reverse("games:create"), _save_game_post(other_group))

    response = client.get(reverse("core:dashboard"))
    content = response.content.decode()

    assert "Leaderboards across your groups" in content
    assert "Dom Club" in content
    assert "Other Club" in content
    assert content.index("Player") < content.index("Group", content.index("Dominos"))
