import pytest
from django.contrib.auth.models import AnonymousUser, User
from django.contrib.sessions.backends.db import SessionStore
from django.test import RequestFactory
from django.urls import reverse

from leaderlodge.accounts.game_selection import (
    GAME_SELECTION_NAMESPACE,
    GAME_TYPE_CODE_KEY,
    SESSION_GAME_TYPE_CODE,
    preferred_game_type_code,
    resolve_game_type_code,
)
from leaderlodge.accounts.models import UserProfile
from leaderlodge.accounts.ui_settings import (
    get_ui_settings,
    reset_ui_settings,
    set_ui_settings,
)


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


@pytest.mark.django_db
def test_user_profile_created_with_user(user):
    assert UserProfile.objects.filter(user=user).exists()


@pytest.mark.django_db
def test_ui_settings_namespace_isolation(user):
    set_ui_settings(user, "game_selection", {"game_type_code": "dominos"})
    set_ui_settings(user, "other", {"foo": "bar"})

    assert get_ui_settings(user, "game_selection") == {"game_type_code": "dominos"}
    assert get_ui_settings(user, "other") == {"foo": "bar"}


@pytest.mark.django_db
def test_reset_ui_settings_clears_all(user):
    set_ui_settings(user, "game_selection", {"game_type_code": "dominos"})
    set_ui_settings(user, "other", {"foo": "bar"})

    reset_ui_settings(user)

    assert user.profile.ui_settings == {}


@pytest.mark.django_db
def test_resolve_game_type_code_saves_first_available_when_no_preference(user, rf):
    request = _request_with_session(rf, user=user)
    chosen = resolve_game_type_code(
        request,
        requested="",
        available_codes=["backgammon", "dominos"],
    )

    assert chosen == "backgammon"
    assert preferred_game_type_code(request) == "backgammon"


@pytest.mark.django_db
def test_resolve_game_type_code_uses_saved_preference(user, rf):
    set_ui_settings(
        user,
        GAME_SELECTION_NAMESPACE,
        {GAME_TYPE_CODE_KEY: "backgammon"},
    )
    request = _request_with_session(rf, user=user)

    chosen = resolve_game_type_code(
        request,
        requested="",
        available_codes=["dominos", "backgammon"],
    )

    assert chosen == "backgammon"


@pytest.mark.django_db
def test_resolve_game_type_code_explicit_selection_overrides_saved(user, rf):
    set_ui_settings(
        user,
        GAME_SELECTION_NAMESPACE,
        {GAME_TYPE_CODE_KEY: "dominos"},
    )
    request = _request_with_session(rf, user=user)

    chosen = resolve_game_type_code(
        request,
        requested="backgammon",
        available_codes=["dominos", "backgammon"],
    )

    assert chosen == "backgammon"
    assert preferred_game_type_code(request) == "backgammon"


@pytest.mark.django_db
def test_resolve_game_type_code_persists_to_session_for_anonymous(rf):
    request = _request_with_session(rf)

    chosen = resolve_game_type_code(
        request,
        requested="backgammon",
        available_codes=["dominos", "backgammon"],
    )

    assert chosen == "backgammon"
    assert request.session[SESSION_GAME_TYPE_CODE] == "backgammon"
    assert preferred_game_type_code(request) == "backgammon"


@pytest.mark.django_db
def test_reset_preferences_endpoint(client, user):
    set_ui_settings(user, "game_selection", {"game_type_code": "dominos"})
    client.force_login(user)

    response = client.post(reverse("accounts:reset_preferences"))

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    user.profile.refresh_from_db()
    assert user.profile.ui_settings == {}


@pytest.mark.django_db
def test_reset_preferences_requires_login(client):
    response = client.post(reverse("accounts:reset_preferences"))

    assert response.status_code == 302
    assert reverse("accounts:login") in response.url
