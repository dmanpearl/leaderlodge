import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from leaderlodge.games.models import Game
from leaderlodge.groups.services import (
    add_guest_player,
    create_group_with_owner,
    editable_groups,
)
from tests.test_games import _load_roster_post, _save_game_post


@pytest.fixture
def user(db):
    return User.objects.create_user(username="david", password="test-pass-123")


@pytest.fixture
def other_user(db):
    return User.objects.create_user(username="pat", password="test-pass-123")


@pytest.fixture
def demo_group(user):
    group = create_group_with_owner(user=user, name="Demo", description="Sample data")
    add_guest_player(group=group, display_name="Pat")
    return group


@pytest.fixture
def demo_group_flagged(demo_group):
    demo_group.is_demo = True
    demo_group.save(update_fields=["is_demo"])
    return demo_group


@pytest.fixture
def member_group(user):
    group = create_group_with_owner(user=user, name="Dom Club")
    add_guest_player(group=group, display_name="Pat")
    return group


@pytest.mark.django_db
def test_anonymous_dashboard_shows_demo_landing(client, demo_group_flagged):
    response = client.get(reverse("core:dashboard"))
    assert response.status_code == 200
    content = response.content.decode()
    assert "Demo" in content
    assert "Sample games and leaderboards for all supported game types." in content
    assert "Record Game" not in content
    assert "Login to view your own Games, Groups, and Leaders" in content
    assert reverse("accounts:login") in content
    assert reverse("accounts:signup") in content
    assert ">Login</a>" in content
    assert ">Sign up</a>" in content


@pytest.mark.django_db
def test_anonymous_dashboard_demo_blurb_when_game_type_locked(
    client, demo_group_flagged
):
    lock = client.get("/?lock=dominos")
    assert lock.status_code == 302
    client.get(lock.url)

    response = client.get(reverse("core:dashboard"))
    assert response.status_code == 200
    content = response.content.decode()
    assert "Sample games and leaderboards." in content
    assert "for all supported game types." not in content


@pytest.mark.django_db
def test_anonymous_can_browse_groups_and_record_game_setup(client, demo_group_flagged):
    demo_group_flagged.description = (
        "Example group with real game data. Login and use '+ Create Group' "
        "to add your own and start logging game scores."
    )
    demo_group_flagged.save(update_fields=["description"])

    list_response = client.get(reverse("groups:list"))
    assert list_response.status_code == 200
    list_content = list_response.content.decode()
    assert "Demo" in list_content
    assert "data-guest-login-prompt" in list_content
    assert "auth_dialog.js" in list_content
    assert "guest-auth-dialog" in list_content
    assert "Create Group" in list_content

    detail_response = client.get(
        reverse("groups:detail", kwargs={"pk": demo_group_flagged.pk})
    )
    assert detail_response.status_code == 200
    assert "Example group with real game data" in detail_response.content.decode()

    create_response = client.get(reverse("games:create"))
    assert create_response.status_code == 200
    create_content = create_response.content.decode()
    assert "Sign in to record" in create_content
    assert "data-guest-login-prompt" in create_content

    roster_response = client.post(
        reverse("games:create"),
        _load_roster_post(demo_group_flagged),
    )
    assert roster_response.status_code == 404


@pytest.mark.django_db
def test_anonymous_can_view_demo_leaderboard(client, demo_group_flagged, user):
    client.force_login(user)
    client.post(reverse("games:create"), _load_roster_post(demo_group_flagged))
    client.post(reverse("games:create"), _save_game_post(demo_group_flagged))
    client.logout()

    response = client.get(
        reverse("leaderboards:index"),
        {"group": str(demo_group_flagged.pk), "type": "dominos"},
    )
    assert response.status_code == 200
    assert "Demo" in response.content.decode()


@pytest.mark.django_db
def test_anonymous_cannot_view_private_group_leaderboard(
    client, member_group, demo_group_flagged, user
):
    client.force_login(user)
    client.post(reverse("games:create"), _load_roster_post(member_group))
    client.post(reverse("games:create"), _save_game_post(member_group))
    client.logout()

    response = client.get(
        reverse("leaderboards:index"),
        {"group": str(member_group.pk), "game_type_code": "dominos"},
        follow=True,
    )
    assert response.status_code == 200
    content = response.content.decode()
    assert "Dom Club" not in content or "Choose a group" in content


@pytest.mark.django_db
def test_other_user_cannot_record_in_demo_group(client, demo_group_flagged, other_user):
    client.force_login(other_user)
    response = client.post(
        reverse("games:create"),
        _load_roster_post(demo_group_flagged),
    )
    assert response.status_code == 404


@pytest.mark.django_db
def test_demo_creator_can_record_in_demo_group(client, demo_group_flagged, user):
    assert demo_group_flagged in editable_groups(user)

    client.force_login(user)
    roster = client.post(
        reverse("games:create"),
        _load_roster_post(demo_group_flagged),
    )
    assert roster.status_code == 200

    save = client.post(
        reverse("games:create"),
        _save_game_post(demo_group_flagged),
    )
    assert save.status_code == 302
    assert Game.objects.filter(group=demo_group_flagged).exists()


@pytest.mark.django_db
def test_staff_can_record_in_demo_group_without_membership(
    client, demo_group_flagged, other_user
):
    other_user.is_staff = True
    other_user.save(update_fields=["is_staff"])
    assert demo_group_flagged in editable_groups(other_user)

    client.force_login(other_user)
    roster = client.post(
        reverse("games:create"),
        _load_roster_post(demo_group_flagged),
    )
    assert roster.status_code == 200

    save = client.post(
        reverse("games:create"),
        _save_game_post(demo_group_flagged),
    )
    assert save.status_code == 302
    assert Game.objects.filter(group=demo_group_flagged).exists()
