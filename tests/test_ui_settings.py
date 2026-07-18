import pytest
from django.contrib.auth.models import AnonymousUser, User
from django.contrib.sessions.backends.db import SessionStore
from django.test import RequestFactory
from django.urls import reverse

from leaderlodge.accounts.game_selection import (
    preferred_game_type_code,
    resolve_game_type_code,
)
from leaderlodge.accounts.ui_settings import (
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
def test_reset_preferences_endpoint(client, user):
    set_ui_settings(user, "game_selection", {"game_type_code": "dominos"})
    client.force_login(user)

    response = client.post(reverse("accounts:reset_preferences"))

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    user.profile.refresh_from_db()
    assert user.profile.ui_settings == {}
