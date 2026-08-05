import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from leaderlodge.games.models import GameParticipantResult
from leaderlodge.games.services import ParticipantInput, record_game
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


@pytest.fixture
def demo_group_flagged(user):
    group = create_group_with_owner(user=user, name="Demo", description="Sample data")
    add_guest_player(group=group, display_name="Pat")
    group.is_demo = True
    group.save(update_fields=["is_demo"])
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
    # Composite mini-leaderboard includes a Group column after Player.
    card_start = content.index("Full Dominos Leaderboard")
    assert content.index("Player", card_start) < content.index("Group", card_start)


@pytest.mark.django_db
def test_dashboard_leaderboard_card_has_record_and_fullscreen_buttons(
    client, user, group
):
    client.force_login(user)
    client.post(reverse("games:create"), _load_roster_post(group))
    client.post(reverse("games:create"), _save_game_post(group))

    content = client.get(reverse("core:dashboard")).content.decode()

    create_url = reverse("games:create")
    assert f'href="{create_url}?type=dominos&group={group.pk}"' in content
    assert "bi-plus-lg" in content
    assert "bi-fullscreen" in content


@pytest.mark.django_db
def test_dashboard_composite_leaderboard_record_button_omits_group(client, user, group):
    other_group = create_group_with_owner(user=user, name="Other Club")
    add_guest_player(group=other_group, display_name="Pat")

    client.force_login(user)
    client.post(reverse("games:create"), _load_roster_post(group))
    client.post(reverse("games:create"), _save_game_post(group))
    client.post(reverse("games:create"), _load_roster_post(other_group))
    client.post(reverse("games:create"), _save_game_post(other_group))

    content = client.get(reverse("core:dashboard")).content.decode()

    create_url = reverse("games:create")
    assert f'href="{create_url}?type=dominos"' in content
    assert f'href="{create_url}?type=dominos&group=' not in content


@pytest.mark.django_db
def test_dashboard_recent_games_header_has_record_and_view_all_buttons(
    client, user, group
):
    client.force_login(user)
    content = client.get(reverse("core:dashboard")).content.decode()

    create_url = reverse("games:create")
    games_list_url = reverse("games:list")
    assert f'href="{create_url}?group={group.pk}"' in content
    assert f'title="Record game"' in content
    assert f'href="{games_list_url}"' in content
    assert 'title="View all games"' in content
    assert ">View all<" not in content


@pytest.mark.django_db
def test_dashboard_recent_games_header_hides_record_button_when_not_can_record(
    client, user, demo_group_flagged
):
    owner, guest = list(demo_group_flagged.players.order_by("pk"))
    record_game(
        user=user,
        group=demo_group_flagged,
        game_type_code="dominos",
        played_on="2026-01-01",
        participants=[
            ParticipantInput(
                player=owner,
                score=30,
                result=GameParticipantResult.Result.WIN,
                placement=0,
            ),
            ParticipantInput(
                player=guest,
                score=20,
                result=GameParticipantResult.Result.PLAYED,
                placement=1,
            ),
        ],
    )

    content = client.get(reverse("core:dashboard")).content.decode()

    assert 'title="View all games"' in content
    assert 'title="Record game"' not in content


@pytest.mark.django_db
def test_dashboard_hides_collapse_when_single_game_type_card(client, user, group):
    client.force_login(user)
    client.post(reverse("games:create"), _load_roster_post(group))
    client.post(reverse("games:create"), _save_game_post(group))

    response = client.get(reverse("core:dashboard"))
    content = response.content.decode()

    assert response.context["dashboard_sections_collapsible"] is False
    assert 'data-bs-toggle="collapse"' not in content
    assert "dashboard-recent-games-icon" not in content
    assert "bi-chevron-right" not in content


@pytest.mark.django_db
def test_dashboard_keeps_collapse_when_multiple_game_type_cards(client, user, group):
    client.force_login(user)
    client.post(reverse("games:create"), _load_roster_post(group))
    client.post(reverse("games:create"), _save_game_post(group))
    client.post(
        reverse("games:create"),
        _load_roster_post(group, game_type_code="pickleball"),
    )
    client.post(
        reverse("games:create"),
        _save_game_post(group, game_type_code="pickleball"),
    )

    response = client.get(reverse("core:dashboard"))
    content = response.content.decode()

    assert response.context["dashboard_sections_collapsible"] is True
    assert 'data-bs-toggle="collapse"' in content
    assert "dashboard-recent-games-icon" in content


@pytest.mark.django_db
def test_dashboard_locked_title_uses_game_type_name(client, user, group):
    client.force_login(user)
    client.get("/?lock=dominos")
    response = client.get(reverse("core:dashboard"))
    content = response.content.decode()

    assert response.context["dashboard_heading"] == "Dominos"
    assert response.context["dashboard_heading_icon_url"]
    assert "game-detail-title-icon" in content
    assert ">Dominos</h1>" in content
    assert "Dashboard" not in content


@pytest.mark.django_db
def test_dashboard_leaderboard_card_hides_record_button_when_not_can_record(
    client, user, demo_group_flagged
):
    owner, guest = list(demo_group_flagged.players.order_by("pk"))
    # Seed via the service layer directly: the demo group is excluded from
    # editable_groups, so the record-game form/view rejects it.
    record_game(
        user=user,
        group=demo_group_flagged,
        game_type_code="dominos",
        played_on="2026-01-01",
        participants=[
            ParticipantInput(
                player=owner,
                score=30,
                result=GameParticipantResult.Result.WIN,
                placement=0,
            ),
            ParticipantInput(
                player=guest,
                score=20,
                result=GameParticipantResult.Result.PLAYED,
                placement=1,
            ),
        ],
    )

    content = client.get(reverse("core:dashboard")).content.decode()

    assert "bi-fullscreen" in content
    assert "Record Dominos game" not in content
