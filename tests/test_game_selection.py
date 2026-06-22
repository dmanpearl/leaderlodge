import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from leaderlodge.accounts.game_selection import (
    GAME_SELECTION_NAMESPACE,
    GAME_TYPE_CODE_KEY,
)
from leaderlodge.accounts.ui_settings import set_ui_settings
from leaderlodge.groups.services import add_guest_player, create_group_with_owner
from tests.test_games import _load_roster_post, _save_game_post


@pytest.fixture
def demo_group_flagged(user):
    group = create_group_with_owner(user=user, name="Demo", description="Sample data")
    add_guest_player(group=group, display_name="Pat")
    group.is_demo = True
    group.save(update_fields=["is_demo"])
    return group


@pytest.fixture
def user(db):
    return User.objects.create_user(username="david", password="test-pass-123")


@pytest.fixture
def group(user):
    group = create_group_with_owner(user=user, name="Dom Club")
    add_guest_player(group=group, display_name="Pat")
    return group


@pytest.mark.django_db
def test_game_list_redirects_to_saved_game_type(client, user, group):
    set_ui_settings(
        user,
        GAME_SELECTION_NAMESPACE,
        {GAME_TYPE_CODE_KEY: "backgammon"},
    )
    client.force_login(user)

    response = client.get(reverse("games:list"))

    assert response.status_code == 302
    assert "game_type=backgammon" in response.url


@pytest.mark.django_db
def test_game_list_persists_explicit_selection(client, user, group):
    client.force_login(user)
    client.post(reverse("games:create"), _load_roster_post(group))
    client.post(reverse("games:create"), _save_game_post(group, game_type_code="dominos"))

    response = client.get(
        reverse("games:list"),
        {"game_type": "backgammon"},
        follow=True,
    )

    assert response.status_code == 200
    from leaderlodge.accounts.ui_settings import get_ui_settings

    assert get_ui_settings(user, GAME_SELECTION_NAMESPACE)[GAME_TYPE_CODE_KEY] == "backgammon"


@pytest.mark.django_db
def test_record_game_form_uses_saved_game_type(client, user, group):
    set_ui_settings(
        user,
        GAME_SELECTION_NAMESPACE,
        {GAME_TYPE_CODE_KEY: "backgammon"},
    )
    client.force_login(user)

    response = client.get(reverse("games:create"))

    assert response.status_code == 200
    assert 'value="backgammon" selected' in response.content.decode()


@pytest.mark.django_db
def test_leaderboard_uses_saved_game_type(client, user, group):
    set_ui_settings(
        user,
        GAME_SELECTION_NAMESPACE,
        {GAME_TYPE_CODE_KEY: "backgammon"},
    )
    client.force_login(user)
    client.post(reverse("games:create"), _load_roster_post(group))
    client.post(reverse("games:create"), _save_game_post(group, game_type_code="dominos"))
    client.post(
        reverse("games:create"),
        _load_roster_post(group, game_type_code="backgammon"),
    )
    client.post(
        reverse("games:create"),
        _save_game_post(group, game_type_code="backgammon"),
    )

    response = client.get(
        reverse("leaderboards:index"),
        {"group": str(group.pk)},
        follow=True,
    )

    assert response.status_code == 200
    content = response.content.decode()
    assert 'value="backgammon" selected' in content


@pytest.mark.django_db
def test_navbar_links_include_saved_game_type(client, user, group):
    set_ui_settings(
        user,
        GAME_SELECTION_NAMESPACE,
        {GAME_TYPE_CODE_KEY: "dominos"},
    )
    client.force_login(user)

    response = client.get(reverse("core:dashboard"))
    content = response.content.decode()

    assert "game_type=dominos" in content
    assert "game_type_code=dominos" in content
    assert "Reset Preferences" in content


@pytest.mark.django_db
def test_anonymous_visitor_maintains_game_type_in_navbar(
    client, demo_group_flagged, user
):
    client.force_login(user)
    client.post(reverse("games:create"), _load_roster_post(demo_group_flagged))
    client.post(reverse("games:create"), _save_game_post(demo_group_flagged))
    client.logout()

    client.get(
        reverse("games:list"),
        {"game_type": "dominos"},
        follow=True,
    )
    response = client.get(reverse("core:dashboard"))
    content = response.content.decode()

    assert "game_type=dominos" in content
    assert "game_type_code=dominos" in content
