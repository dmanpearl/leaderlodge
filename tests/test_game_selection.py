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
    assert "type=backgammon" in response.url


@pytest.mark.django_db
def test_game_list_persists_explicit_selection(client, user, group):
    client.force_login(user)
    client.post(reverse("games:create"), _load_roster_post(group))
    client.post(
        reverse("games:create"), _save_game_post(group, game_type_code="dominos")
    )

    response = client.get(
        reverse("games:list"),
        {"type": "backgammon"},
        follow=True,
    )

    assert response.status_code == 200
    from leaderlodge.accounts.ui_settings import get_ui_settings

    assert (
        get_ui_settings(user, GAME_SELECTION_NAMESPACE)[GAME_TYPE_CODE_KEY]
        == "backgammon"
    )


@pytest.mark.django_db
def test_record_game_form_uses_saved_game_type(client, user, group):
    set_ui_settings(
        user,
        GAME_SELECTION_NAMESPACE,
        {GAME_TYPE_CODE_KEY: "backgammon"},
    )
    client.force_login(user)

    response = client.get(reverse("games:create"))
    content = response.content.decode()

    assert response.status_code == 200
    assert 'value="backgammon"' in content
    assert (
        "selected" in content.split('value="backgammon"', 1)[1].split("</option>", 1)[0]
    )
    assert "game-setup-game-type-icon" in content
    assert "game-types/backgammon.png" in content


@pytest.mark.django_db
def test_record_game_persists_group_and_game_type(client, user, group):
    """Recording a game updates preferences so Games/Leaders open on that type."""
    from leaderlodge.accounts.group_selection import (
        GROUP_ID_KEY,
        GROUP_SELECTION_NAMESPACE,
    )
    from leaderlodge.accounts.ui_settings import get_ui_settings

    set_ui_settings(
        user,
        GAME_SELECTION_NAMESPACE,
        {GAME_TYPE_CODE_KEY: "backgammon"},
    )
    client.force_login(user)
    client.post(
        reverse("games:create"),
        _load_roster_post(group, game_type_code="dominos"),
    )
    response = client.post(
        reverse("games:create"),
        _save_game_post(group, game_type_code="dominos"),
    )

    assert response.status_code == 302
    assert (
        get_ui_settings(user, GAME_SELECTION_NAMESPACE)[GAME_TYPE_CODE_KEY] == "dominos"
    )
    assert get_ui_settings(user, GROUP_SELECTION_NAMESPACE)[GROUP_ID_KEY] == str(
        group.pk
    )

    list_response = client.get(reverse("games:list"))
    assert list_response.status_code == 302
    assert "type=dominos" in list_response.url
    assert f"group={group.pk}" in list_response.url

    detail = client.get(response.url)
    assert detail.status_code == 200
    assert f"/games/?group={group.pk}&amp;type=dominos" in detail.content.decode()


@pytest.mark.django_db
def test_leaderboard_uses_saved_game_type(client, user, group):
    set_ui_settings(
        user,
        GAME_SELECTION_NAMESPACE,
        {GAME_TYPE_CODE_KEY: "backgammon"},
    )
    client.force_login(user)
    client.post(reverse("games:create"), _load_roster_post(group))
    client.post(
        reverse("games:create"), _save_game_post(group, game_type_code="dominos")
    )
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
    assert 'value="backgammon"' in content
    assert "selected" in content
    assert "Backgammon" in content
    assert f"type=backgammon" in content or "type=backgammon" in content


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

    assert "type=dominos" in content
    assert "type=dominos" in content
