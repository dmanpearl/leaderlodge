"""Staff-facing site metrics. Intentionally ignores game-type lock."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db.models import Count, Q
from django.utils import timezone

from leaderlodge.games.game_type_icons import game_type_icon_url
from leaderlodge.games.models import Game
from leaderlodge.games.registry import GAME_TYPES, get_game_type
from leaderlodge.groups.models import Group

# Easy to find and change: how many top groups the metrics page lists.
METRICS_TOP_GROUPS = 10

ROLLING_DAYS = 7
User = get_user_model()


@dataclass(frozen=True)
class GroupActivityRow:
    group_id: int
    group_name: str
    is_demo: bool
    user_count: int
    games_total: int
    games_last_hour: int
    games_last_7_days: int
    avg_games_per_day: Decimal


@dataclass(frozen=True)
class GameTypeActivityRow:
    game_type_code: str
    game_type_name: str
    icon_url: str
    games_total: int
    games_last_hour: int
    games_last_7_days: int
    avg_games_per_day: Decimal


@dataclass(frozen=True)
class SiteMetrics:
    total_users: int
    group_count: int
    games_total: int
    games_last_hour: int
    avg_games_per_day_7d: Decimal
    top_groups: list[GroupActivityRow]
    game_types: list[GameTypeActivityRow]
    top_n: int
    generated_at: datetime


def _avg_per_day(game_count: int, days: int = ROLLING_DAYS) -> Decimal:
    if days <= 0:
        return Decimal("0")
    return (Decimal(game_count) / Decimal(days)).quantize(Decimal("0.01"))


def _counts_by_game_type(*, since: datetime | None = None) -> dict[str, int]:
    qs = Game.objects.all()
    if since is not None:
        qs = qs.filter(created_at__gte=since)
    return {
        row["game_type_code"]: int(row["n"])
        for row in qs.values("game_type_code").annotate(n=Count("id"))
    }


def _game_type_activity_rows(
    *,
    hour_ago: datetime,
    week_ago: datetime,
) -> list[GameTypeActivityRow]:
    total_counts = _counts_by_game_type()
    hour_counts = _counts_by_game_type(since=hour_ago)
    week_counts = _counts_by_game_type(since=week_ago)

    rows: list[GameTypeActivityRow] = []
    for code in GAME_TYPES:
        total = total_counts.get(code, 0)
        week = week_counts.get(code, 0)
        hour = hour_counts.get(code, 0)
        if total == 0:
            continue
        rows.append(
            GameTypeActivityRow(
                game_type_code=code,
                game_type_name=get_game_type(code).name,
                icon_url=game_type_icon_url(code),
                games_total=total,
                games_last_hour=hour,
                games_last_7_days=week,
                avg_games_per_day=_avg_per_day(week),
            )
        )
    rows.sort(
        key=lambda row: (
            -row.games_total,
            -row.games_last_7_days,
            -row.games_last_hour,
            row.game_type_name,
        )
    )
    return rows


def build_site_metrics(*, top_n: int = METRICS_TOP_GROUPS) -> SiteMetrics:
    """Aggregate site-wide activity using rolling windows (to the minute)."""
    now = timezone.now()
    hour_ago = now - timedelta(hours=1)
    week_ago = now - timedelta(days=ROLLING_DAYS)

    total_users = User.objects.count()
    group_count = Group.objects.count()
    games_total = Game.objects.count()

    games_last_hour = Game.objects.filter(created_at__gte=hour_ago).count()
    games_last_7_days = Game.objects.filter(created_at__gte=week_ago).count()
    avg_games_per_day_7d = _avg_per_day(games_last_7_days)

    # Groups with activity in the rolling 7-day window, ranked by total games.
    ranked = list(
        Group.objects.annotate(
            games_total=Count("games"),
            games_last_7_days=Count(
                "games",
                filter=Q(games__created_at__gte=week_ago),
            ),
            games_last_hour=Count(
                "games",
                filter=Q(games__created_at__gte=hour_ago),
            ),
            user_count=Count("memberships", distinct=True),
        )
        .filter(games_last_7_days__gt=0)
        .order_by("-games_total", "name", "pk")[: max(top_n, 0)]
    )

    top_groups = [
        GroupActivityRow(
            group_id=group.pk,
            group_name=group.name,
            is_demo=bool(group.is_demo),
            user_count=int(group.user_count),
            games_total=int(group.games_total),
            games_last_hour=int(group.games_last_hour),
            games_last_7_days=int(group.games_last_7_days),
            avg_games_per_day=_avg_per_day(int(group.games_last_7_days)),
        )
        for group in ranked
    ]

    return SiteMetrics(
        total_users=total_users,
        group_count=group_count,
        games_total=games_total,
        games_last_hour=games_last_hour,
        avg_games_per_day_7d=avg_games_per_day_7d,
        top_groups=top_groups,
        game_types=_game_type_activity_rows(hour_ago=hour_ago, week_ago=week_ago),
        top_n=top_n,
        generated_at=now,
    )
