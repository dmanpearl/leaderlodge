import pytest
from django.contrib.auth.models import User
from django.test import override_settings
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


def _navbar_main_nav(content: str) -> str:
    start = content.index('class="navbar-nav navbar-nav-main')
    end = content.index("</ul>", start)
    return content[start:end]


def _active_nav_label(main_nav: str) -> str | None:
    markers = (
        'class="nav-link d-inline-flex align-items-center gap-1 active"',
        'class="nav-link navbar-nav-link--insights d-inline-flex align-items-center gap-1 active"',
    )
    for marker in markers:
        if marker not in main_nav:
            continue
        section = main_nav.split(marker, 1)[1]
        anchor = section.split("</a>", 1)[0]
        if 'aria-label="Games"' in anchor:
            return "games"
        if 'aria-label="Leaders"' in anchor:
            return "leaders"
        if 'aria-label="Groups"' in anchor:
            return "groups"
        if 'aria-label="Add"' in anchor:
            return "add"
        if 'aria-label="Ask"' in anchor:
            return "insights"
        return "unknown"
    return None


@pytest.mark.django_db
def test_navbar_highlights_games_on_game_list(client, user, group):
    client.force_login(user)
    content = client.get(reverse("games:list"), follow=True).content.decode()
    assert _active_nav_label(_navbar_main_nav(content)) == "games"


@pytest.mark.django_db
def test_navbar_highlights_add_on_record_game(client, user, group):
    client.force_login(user)
    content = client.get(
        reverse("games:create"),
        {"group": str(group.pk)},
        follow=True,
    ).content.decode()
    assert _active_nav_label(_navbar_main_nav(content)) == "add"


@pytest.mark.django_db
def test_navbar_highlights_leaders_on_leaderboard(client, user, group):
    client.force_login(user)
    content = client.get(
        reverse("leaderboards:index"),
        {"group": str(group.pk), "game_type_code": "dominos"},
        follow=True,
    ).content.decode()
    assert _active_nav_label(_navbar_main_nav(content)) == "leaders"


@pytest.mark.django_db
def test_navbar_highlights_leaders_on_hall_of_fame(client, user, group):
    client.force_login(user)
    client.post(reverse("games:create"), _load_roster_post(group))
    client.post(reverse("games:create"), _save_game_post(group))

    content = client.get(
        reverse("leaderboards:hall_of_fame"),
        {"group": str(group.pk)},
        follow=True,
    ).content.decode()
    assert _active_nav_label(_navbar_main_nav(content)) == "leaders"


@pytest.mark.django_db
def test_navbar_highlights_groups_on_group_list(client, user):
    client.force_login(user)
    content = client.get(reverse("groups:list")).content.decode()
    assert _active_nav_label(_navbar_main_nav(content)) == "groups"


@pytest.mark.django_db
def test_navbar_does_not_highlight_main_nav_on_dashboard(client, user):
    client.force_login(user)
    content = client.get(reverse("core:dashboard")).content.decode()
    assert 'navbar-nav-main' in content
    assert ' active"' not in _navbar_main_nav(content)


@pytest.mark.django_db
@override_settings(
    INSIGHTS_ENABLED=True,
    OPENAI_API_KEY="test-openai",
    GOOGLE_AI_API_KEY="test-google",
)
def test_navbar_shows_insights_link(client, user, group):
    client.force_login(user)
    client.post(reverse("games:create"), _load_roster_post(group))
    client.post(reverse("games:create"), _save_game_post(group))

    content = client.get(reverse("core:dashboard")).content.decode()
    main_nav = _navbar_main_nav(content)
    assert 'aria-label="Ask"' in main_nav
    assert "bi-stars" in main_nav
    assert ">Ask</span>" in main_nav
    assert 'navbar-brand-logo d-none d-md-block' in content


@pytest.mark.django_db
@override_settings(
    INSIGHTS_ENABLED=True,
    OPENAI_API_KEY="test-openai",
    GOOGLE_AI_API_KEY="test-google",
)
def test_navbar_highlights_insights_on_ask_page(client, user, group):
    client.force_login(user)
    client.post(reverse("games:create"), _load_roster_post(group))
    client.post(reverse("games:create"), _save_game_post(group))

    content = client.get(
        reverse("insights:ask"),
        {"group": str(group.pk), "game_type_code": "dominos"},
    ).content.decode()
    assert _active_nav_label(_navbar_main_nav(content)) == "insights"
