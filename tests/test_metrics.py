from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone

from leaderlodge.core.metrics import METRICS_TOP_GROUPS, build_site_metrics
from leaderlodge.games.models import Game, GameParticipantResult
from leaderlodge.groups.services import add_guest_player, create_group_with_owner


@pytest.fixture
def staff_user(db):
    return User.objects.create_user(
        username="staffer",
        password="test-pass-123",
        is_staff=True,
    )


@pytest.fixture
def plain_user(db):
    return User.objects.create_user(username="member", password="test-pass-123")


def _record_game(user, group, *, created_at=None, game_type_code="dominos"):
    players = list(group.players.order_by("pk"))
    while len(players) < 2:
        players.append(add_guest_player(group=group, display_name=f"P{len(players)}"))
    game = Game.objects.create(
        group=group,
        game_type_code=game_type_code,
        played_on=timezone.localdate(),
        recorded_by=user,
        player_count=2,
    )
    if created_at is not None:
        Game.objects.filter(pk=game.pk).update(created_at=created_at)
        game.refresh_from_db()
    GameParticipantResult.objects.create(
        game=game,
        player=players[0],
        score=30,
        result=GameParticipantResult.Result.WIN,
        placement=0,
    )
    GameParticipantResult.objects.create(
        game=game,
        player=players[1],
        score=20,
        result=GameParticipantResult.Result.PLAYED,
        placement=1,
    )
    return game


@pytest.mark.django_db
def test_metrics_requires_staff(client, plain_user):
    client.force_login(plain_user)
    response = client.get(reverse("core:metrics"))
    assert response.status_code == 403


@pytest.mark.django_db
def test_metrics_requires_login(client):
    response = client.get(reverse("core:metrics"))
    assert response.status_code == 302
    assert reverse("accounts:login") in response.url


@pytest.mark.django_db
def test_metrics_page_and_menu_for_staff(client, staff_user):
    client.force_login(staff_user)
    dash = client.get(reverse("core:dashboard")).content.decode()
    assert reverse("core:metrics") in dash
    assert "Metrics" in dash

    response = client.get(reverse("core:metrics"))
    assert response.status_code == 200
    content = response.content.decode()
    assert ">Metrics</h1>" in content
    assert "Total users" in content
    assert "Total games" in content
    assert "Top" in content
    assert "Games by type" in content
    assert 'id="metrics-groups-panel"' in content
    assert 'id="metrics-games-panel"' in content
    assert "metrics.js" in content


@pytest.mark.django_db
def test_build_site_metrics_counts_and_top_groups(staff_user):
    now = timezone.now()
    active = create_group_with_owner(user=staff_user, name="Active Club")
    quiet = create_group_with_owner(user=staff_user, name="Quiet Club")
    add_guest_player(group=active, display_name="Pat")
    add_guest_player(group=quiet, display_name="Sam")

    for offset_minutes in (5, 10, 20):
        _record_game(
            staff_user,
            active,
            created_at=now - timedelta(minutes=offset_minutes),
        )
    _record_game(
        staff_user,
        active,
        created_at=now - timedelta(days=2),
        game_type_code="pickleball",
    )
    _record_game(
        staff_user,
        quiet,
        created_at=now - timedelta(days=3),
    )
    # Outside the rolling windows.
    _record_game(
        staff_user,
        quiet,
        created_at=now - timedelta(days=10),
    )

    metrics = build_site_metrics(top_n=METRICS_TOP_GROUPS)
    assert metrics.total_users >= 1
    assert metrics.group_count >= 2
    assert metrics.games_total == 6
    assert metrics.games_last_hour == 3
    # 4 games in last 7 days for active + 1 for quiet = 5 site-wide in window
    assert metrics.avg_games_per_day_7d == Decimal("0.71")

    assert [row.group_name for row in metrics.top_groups][:2] == [
        "Active Club",
        "Quiet Club",
    ]
    top = metrics.top_groups[0]
    assert top.games_total == 4
    assert top.games_last_hour == 3
    assert top.games_last_7_days == 4
    assert top.avg_games_per_day == Decimal("0.57")
    assert top.user_count >= 1
    quiet_row = metrics.top_groups[1]
    assert quiet_row.games_total == 2

    by_type = {row.game_type_code: row for row in metrics.game_types}
    assert set(by_type) == {"dominos", "pickleball"}
    assert by_type["dominos"].games_total == 5
    assert by_type["dominos"].games_last_hour == 3
    assert by_type["dominos"].games_last_7_days == 4
    assert by_type["dominos"].avg_games_per_day == Decimal("0.57")
    assert by_type["pickleball"].games_total == 1
    assert by_type["pickleball"].games_last_hour == 0
    assert by_type["pickleball"].games_last_7_days == 1
    assert [row.game_type_code for row in metrics.game_types][0] == "dominos"


@pytest.mark.django_db
def test_metrics_ignores_game_type_lock(client, staff_user):
    active = create_group_with_owner(user=staff_user, name="Mixed")
    add_guest_player(group=active, display_name="Pat")
    now = timezone.now()
    _record_game(staff_user, active, created_at=now - timedelta(minutes=3))
    _record_game(
        staff_user,
        active,
        created_at=now - timedelta(minutes=4),
        game_type_code="pickleball",
    )

    client.force_login(staff_user)
    client.get("/?lock=dominos")
    response = client.get(reverse("core:metrics"))
    assert response.status_code == 200
    assert response.context["metrics"].games_last_hour == 2
