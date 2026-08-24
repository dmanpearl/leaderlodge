import pytest
from django.contrib.auth.models import AnonymousUser, User
from django.contrib.sessions.backends.db import SessionStore
from django.test import RequestFactory
from django.urls import reverse

from leaderlodge.accounts.group_selection import (
    GROUP_ID_KEY,
    GROUP_SELECTION_NAMESPACE,
    preferred_group_id,
    resolve_group_id,
)
from leaderlodge.accounts.ui_settings import set_ui_settings
from leaderlodge.groups.services import add_guest_player, create_group_with_owner
from tests.test_games import _load_roster_post, _save_game_post


@pytest.fixture
def user(db):
    return User.objects.create_user(username="david", password="test-pass-123")


@pytest.fixture
def rf():
    return RequestFactory()


def _request_with_session(rf, *, user=None):
    request = rf.get("/")
    request.user = user if user is not None else AnonymousUser()
    session = SessionStore()
    session.create()
    request.session = session
    return request


@pytest.fixture
def group(user):
    group = create_group_with_owner(user=user, name="Dom Club")
    add_guest_player(group=group, display_name="Pat")
    return group


@pytest.fixture
def other_group(user):
    group = create_group_with_owner(user=user, name="manpearl")
    add_guest_player(group=group, display_name="Pat")
    return group


@pytest.fixture
def demo_group_flagged(user):
    group = create_group_with_owner(user=user, name="Demo", description="Sample data")
    add_guest_player(group=group, display_name="Pat")
    group.is_demo = True
    group.save(update_fields=["is_demo"])
    return group


@pytest.mark.django_db
def test_resolve_group_id_persists_first_available_when_no_preference(
    user, group, other_group, rf
):
    request = _request_with_session(rf, user=user)

    chosen = resolve_group_id(
        request,
        requested=None,
        available_groups=[group, other_group],
    )

    assert chosen == str(group.pk)
    assert preferred_group_id(request) == str(group.pk)


@pytest.mark.django_db
def test_game_list_always_redirects_to_specific_group(client, user, group, other_group):
    set_ui_settings(
        user,
        GROUP_SELECTION_NAMESPACE,
        {GROUP_ID_KEY: str(other_group.pk)},
    )
    client.force_login(user)

    response = client.get(reverse("games:list"))

    assert response.status_code == 302
    assert f"group={other_group.pk}" in response.url
    assert "All groups" not in client.get(response.url, follow=True).content.decode()


@pytest.mark.django_db
def test_leaderboard_redirects_to_saved_group_not_first_alphabetical(
    client, user, group, other_group
):
    set_ui_settings(
        user,
        GROUP_SELECTION_NAMESPACE,
        {GROUP_ID_KEY: str(other_group.pk)},
    )
    client.force_login(user)
    client.post(reverse("games:create"), _load_roster_post(other_group))
    client.post(reverse("games:create"), _save_game_post(other_group))

    response = client.get(reverse("leaderboards:index"))

    assert response.status_code == 302
    assert f"group={other_group.pk}" in response.url
    assert f"group={group.pk}" not in response.url


@pytest.mark.django_db
def test_games_and_leaders_share_group_preference(client, user, group, other_group):
    client.force_login(user)
    client.post(reverse("games:create"), _load_roster_post(other_group))
    client.post(reverse("games:create"), _save_game_post(other_group))

    client.get(
        reverse("games:list"),
        {"group": str(other_group.pk), "game_type": "dominos"},
        follow=True,
    )
    response = client.get(reverse("leaderboards:index"), follow=True)

    assert response.status_code == 200
    content = response.content.decode()
    assert f'value="{other_group.pk}" selected' in content
    assert "manpearl" in content


@pytest.mark.django_db
def test_navbar_links_include_saved_group(client, user, group, other_group):
    set_ui_settings(
        user,
        GROUP_SELECTION_NAMESPACE,
        {GROUP_ID_KEY: str(other_group.pk)},
    )
    set_ui_settings(
        user,
        "game_selection",
        {"game_type_code": "dominos"},
    )
    client.force_login(user)

    response = client.get(reverse("core:dashboard"))
    content = response.content.decode()

    assert f"group={other_group.pk}" in content
    assert "game_type=dominos" in content
    assert "type=dominos" in content


@pytest.mark.django_db
def test_navbar_mobile_brand_and_account_record_game(client, user, group):
    client.force_login(user)
    content = client.get(reverse("core:dashboard")).content.decode()

    assert "navbar-brand-duck" in content
    assert (
        'class="navbar-brand-sr-only-mobile visually-hidden">LeaderLodge</span>'
        in content
    )
    assert "Ask the Lodge" in content
    assert "Record game" in content


@pytest.mark.django_db
def test_anonymous_visitor_maintains_group_between_views(
    client, demo_group_flagged, user
):
    client.force_login(user)
    client.post(reverse("games:create"), _load_roster_post(demo_group_flagged))
    client.post(reverse("games:create"), _save_game_post(demo_group_flagged))
    client.logout()

    client.get(
        reverse("leaderboards:index"),
        {"group": str(demo_group_flagged.pk), "game_type_code": "dominos"},
        follow=True,
    )
    response = client.get(reverse("core:dashboard"))
    content = response.content.decode()

    assert f"group={demo_group_flagged.pk}" in content
