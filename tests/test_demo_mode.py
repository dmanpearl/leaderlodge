import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from leaderlodge.games.services import ParticipantInput, record_game
from leaderlodge.groups.services import add_guest_player, create_group_with_owner
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
def test_anonymous_dashboard_requires_login_without_demo(client):
    response = client.get(reverse("core:dashboard"))
    assert response.status_code == 302
    assert reverse("accounts:login") in response.url


@pytest.mark.django_db
def test_anonymous_dashboard_shows_demo_landing(client, demo_group_flagged):
    response = client.get(reverse("core:dashboard"))
    assert response.status_code == 200
    content = response.content.decode()
    assert "Demo" in content
    assert "Sample games" in content
    assert "Record Game" not in content
    assert "Login to view your own Games, Groups, and Leaders" in content


@pytest.mark.django_db
def test_anonymous_can_browse_groups_and_record_game_setup(client, demo_group_flagged):
    demo_group_flagged.description = (
        "Test group with example game data. Login and use '+ Create Group' "
        "to add your own and start logging game scores."
    )
    demo_group_flagged.save(update_fields=["description"])

    list_response = client.get(reverse("groups:list"))
    assert list_response.status_code == 200
    list_content = list_response.content.decode()
    assert "Demo" in list_content
    assert "data-guest-login-prompt" in list_content
    assert "Create Group" in list_content

    detail_response = client.get(
        reverse("groups:detail", kwargs={"pk": demo_group_flagged.pk})
    )
    assert detail_response.status_code == 200
    assert "Test group with example game data" in detail_response.content.decode()

    create_response = client.get(reverse("games:create"))
    assert create_response.status_code == 200
    create_content = create_response.content.decode()
    assert "Pick Players" in create_content
    assert "data-guest-login-prompt" in create_content

    roster_response = client.post(
        reverse("games:create"),
        _load_roster_post(demo_group_flagged),
    )
    assert roster_response.status_code == 404


@pytest.mark.django_db
def test_anonymous_groups_list_requires_login_without_demo(client):
    response = client.get(reverse("groups:list"))
    assert response.status_code == 302
    assert reverse("accounts:login") in response.url


@pytest.mark.django_db
def test_anonymous_can_view_demo_leaderboard(client, demo_group_flagged, user):
    client.force_login(user)
    client.post(reverse("games:create"), _load_roster_post(demo_group_flagged))
    client.post(reverse("games:create"), _save_game_post(demo_group_flagged))
    client.logout()

    response = client.get(
        reverse("leaderboards:index"),
        {"group": str(demo_group_flagged.pk), "game_type_code": "dominos"},
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
def test_other_user_cannot_record_in_demo_group(
    client, demo_group_flagged, other_user
):
    client.force_login(other_user)
    response = client.post(
        reverse("games:create"),
        _load_roster_post(demo_group_flagged),
    )
    assert response.status_code == 404


@pytest.mark.django_db
def test_demo_owner_can_import_via_record_game(user, demo_group_flagged):
    players = list(demo_group_flagged.players.order_by("pk"))
    rows = [
        ParticipantInput(
            player=players[0],
            score=30,
            result="win",
            placement=0,
        ),
        ParticipantInput(
            player=players[1],
            score=20,
            result="played",
            placement=1,
        ),
    ]
    from datetime import date

    game = record_game(
        user=user,
        group=demo_group_flagged,
        game_type_code="dominos",
        played_on=date(2026, 6, 1),
        participants=rows,
    )
    assert game.group_id == demo_group_flagged.pk


@pytest.mark.django_db
def test_navbar_shows_groups_and_add_for_anonymous_when_demo_enabled(
    client, demo_group_flagged
):
    response = client.get(reverse("core:dashboard"))
    content = response.content.decode()
    assert reverse("games:list") in content
    assert reverse("leaderboards:index") in content
    assert reverse("groups:list") in content
    assert reverse("games:create") in content


@pytest.mark.django_db
def test_logged_in_demo_owner_can_open_games_list(client, user, demo_group_flagged):
    client.force_login(user)
    response = client.get(reverse("games:list"))
    assert response.status_code in (200, 302)
    if response.status_code == 302:
        response = client.get(response.url)
    assert response.status_code == 200
