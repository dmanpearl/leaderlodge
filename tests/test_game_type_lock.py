import pytest
from django.test import Client, override_settings
from django.urls import reverse

from leaderlodge.accounts.game_selection import (
    available_game_type_codes,
    is_game_type_locked,
    lock_game_type,
    locked_game_type_code,
    preferred_game_type_code,
    unlock_game_type,
)
from leaderlodge.games.registry import (
    GAME_TYPES,
    game_type_abbr,
    resolve_game_type_token,
)
from leaderlodge.groups.services import create_group_with_owner


@pytest.mark.parametrize(
    ("token", "expected"),
    [
        ("dominos", "dominos"),
        ("DO", "dominos"),
        ("do", "dominos"),
        ("pt", "phase10"),
        ("PT", "phase10"),
        ("phase10", "phase10"),
        ("", None),
        ("nope", None),
    ],
)
def test_resolve_game_type_token(token, expected):
    assert resolve_game_type_token(token) == expected


def test_every_game_type_has_unique_abbr():
    abbrs = [gt.abbr.upper() for gt in GAME_TYPES.values()]
    assert len(abbrs) == len(set(abbrs))
    for gt in GAME_TYPES.values():
        assert game_type_abbr(gt.code) == gt.abbr


@pytest.mark.django_db
def test_lock_unlock_session_for_anonymous(client: Client):
    session = client.session
    session.save()
    request = client.get("/").wsgi_request
    # Build a request with session via login-less API helpers through a view.
    # Use the test client middleware path instead.
    response = client.get("/?lock=do")
    assert response.status_code == 302
    assert "lock=" not in response.url
    # Follow to apply cookie/session
    client.get(response.url)
    # Inspect via a second request that exposes preference through dashboard
    response = client.get(reverse("core:about"))
    assert response.status_code == 200
    assert response.context["game_type_locked"] is True


@pytest.mark.django_db
def test_lock_type_unlock_url_flow(client: Client, django_user_model):
    user = django_user_model.objects.create_user(
        username="locker", password="test-pass-123"
    )
    create_group_with_owner(user=user, name="Club")
    client.force_login(user)

    r = client.get("/?l=dominos")
    assert r.status_code == 302
    client.get(r.url)
    about = client.get(reverse("core:about"))
    assert about.context["game_type_locked"] is True

    # Same type while locked: no unlock
    r = client.get("/games/?type=dominos")
    assert r.status_code in (200, 302)
    about = client.get(reverse("core:about"))
    assert about.context["game_type_locked"] is True

    # Different type unlocks and switches preference
    r = client.get("/?t=darts")
    assert r.status_code in (200, 302)
    about = client.get(reverse("core:about"))
    assert about.context["game_type_locked"] is False

    # Lock again, then unlock flag
    client.get("/?lock=pb")
    about = client.get(reverse("core:about"))
    assert about.context["game_type_locked"] is True
    r = client.get("/?unlock")
    assert r.status_code == 302
    assert "unlock" not in r.url
    client.get(r.url)
    about = client.get(reverse("core:about"))
    assert about.context["game_type_locked"] is False


@pytest.mark.django_db
def test_account_lock_unlock_posts(client: Client, django_user_model):
    user = django_user_model.objects.create_user(
        username="locker2", password="test-pass-123"
    )
    create_group_with_owner(user=user, name="Club")
    client.force_login(user)
    client.get("/?type=cribbage")

    r = client.post(reverse("accounts:lock_game_type"), {"next": "/about/"})
    assert r.status_code == 302
    about = client.get(reverse("core:about"))
    assert about.context["game_type_locked"] is True

    r = client.post(reverse("accounts:unlock_game_type"), {"next": "/about/"})
    assert r.status_code == 302
    about = client.get(reverse("core:about"))
    assert about.context["game_type_locked"] is False


@pytest.mark.django_db
def test_available_codes_when_locked(rf, django_user_model):
    user = django_user_model.objects.create_user(
        username="locker3", password="test-pass-123"
    )
    request = rf.get("/")
    request.user = user
    request.session = {}
    lock_game_type(request, "ginrummy")
    assert is_game_type_locked(request)
    assert locked_game_type_code(request) == "ginrummy"
    assert available_game_type_codes(request) == ["ginrummy"]
    unlock_game_type(request)
    assert not is_game_type_locked(request)
    assert preferred_game_type_code(request) == "ginrummy"


@pytest.mark.django_db
@override_settings(INSIGHTS_ENABLED=True, OPENAI_API_KEY="test-key")
def test_locked_hides_game_filter_and_updates_titles(client: Client, django_user_model):
    user = django_user_model.objects.create_user(
        username="locker4", password="test-pass-123"
    )
    create_group_with_owner(user=user, name="Club")
    client.force_login(user)
    client.get("/?lock=dominos")

    nav = client.get(reverse("core:dashboard")).content.decode()
    assert "Unlock: Show all game types" in nav
    assert "Show Dominos only" not in nav
    assert "Lock: Dominos only" not in nav
    assert "Lock Game Type" not in nav

    create = client.get(reverse("games:create")).content.decode()
    assert "Dominos - Record Game" in create
    assert "game-detail-title-icon" in create
    assert "game-setup-game-type-wrap" not in create
    assert 'name="game_type_code"' in create
    assert 'type="hidden"' in create
    assert 'value="dominos"' in create

    leaderboard = client.get(
        reverse("leaderboards:index"), follow=True
    ).content.decode()
    assert 'id="game-type-select"' not in leaderboard
    assert 'for="game-type-select"' not in leaderboard
    assert "game-detail-title-icon" in leaderboard
    assert ">Dominos</h1>" in leaderboard

    map_page = client.get(reverse("games:map"), follow=True).content.decode()
    assert 'id="map-game-type-select"' not in map_page
    assert "game-detail-title-icon" in map_page
    assert ">Dominos</h1>" in map_page
    assert ">Map</h1>" not in map_page

    ask = client.get(reverse("insights:ask"), follow=True).content.decode()
    assert 'id="ask-game-type"' not in ask
    assert 'for="ask-game-type"' not in ask


@pytest.mark.django_db
@pytest.mark.parametrize("lock_code", ["progressiverummy", "mahjongg"])
def test_locked_games_list_title_is_single_line_span(
    client: Client, django_user_model, lock_code
):
    user = django_user_model.objects.create_user(
        username=f"locker-{lock_code}", password="test-pass-123"
    )
    create_group_with_owner(user=user, name="Club")
    client.force_login(user)
    client.get(f"/?lock={lock_code}")

    page = client.get(reverse("games:list"), follow=True).content.decode()
    name = GAME_TYPES[lock_code].name
    assert name in page
    assert (
        '<span class="game-list-title-select form-select" id="filter-game-type"' in page
    )
    assert 'select\n            id="filter-game-type"' not in page


@pytest.mark.django_db
def test_account_menu_lock_label_uses_preferred_type(client: Client, django_user_model):
    user = django_user_model.objects.create_user(
        username="locker5", password="test-pass-123"
    )
    create_group_with_owner(user=user, name="Club")
    client.force_login(user)
    client.get("/?type=pickleball")

    content = client.get(reverse("core:dashboard")).content.decode()
    assert "Lock: Pickleball only" in content
    assert "Unlock: Show all game types" not in content
    assert "Show Pickleball only" not in content
