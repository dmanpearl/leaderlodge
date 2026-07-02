from __future__ import annotations

import calendar
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING
from urllib.parse import urlencode

if TYPE_CHECKING:
    from django.db.models import QuerySet

    from leaderlodge.groups.models import Group


@dataclass(frozen=True)
class LeaderboardPeriod:
    year: int | None = None
    month: int | None = None

    @classmethod
    def all_time(cls) -> LeaderboardPeriod:
        return cls()

    @property
    def is_filtered(self) -> bool:
        return self.year is not None

    @property
    def apply_vesting(self) -> bool:
        return not self.is_filtered

    def query_params(self) -> dict[str, str]:
        params: dict[str, str] = {}
        if self.year is not None:
            params["year"] = str(self.year)
        if self.month is not None:
            params["month"] = str(self.month)
        return params

    def display_label(self) -> str:
        if self.month is not None and self.year is not None:
            return f"{calendar.month_name[self.month]} {self.year}"
        if self.year is not None:
            return str(self.year)
        return ""


def available_leaderboard_periods(
    group: Group,
    game_type_code: str,
) -> tuple[list[int], dict[int, tuple[int, ...]]]:
    from leaderlodge.games.models import Game

    dates = (
        Game.objects.filter(group=group, game_type_code=game_type_code)
        .values_list("played_on", flat=True)
        .distinct()
    )
    months_by_year: dict[int, set[int]] = defaultdict(set)
    for played_on in dates:
        months_by_year[played_on.year].add(played_on.month)

    years = sorted(months_by_year.keys(), reverse=True)
    months = {year: tuple(sorted(months_by_year[year], reverse=True)) for year in years}
    return years, months


def resolve_leaderboard_period(
    *,
    raw_year: str,
    raw_month: str,
    available_years: list[int],
    months_by_year: dict[int, tuple[int, ...]],
) -> LeaderboardPeriod:
    year: int | None = None
    if raw_year.isdigit():
        candidate = int(raw_year)
        if candidate in available_years:
            year = candidate

    month: int | None = None
    if year is not None and raw_month.isdigit():
        candidate = int(raw_month)
        if candidate in months_by_year.get(year, ()):
            month = candidate

    return LeaderboardPeriod(year=year, month=month)


def filter_results_by_period(
    results_qs: QuerySet,
    period: LeaderboardPeriod,
    *,
    game_prefix: str = "game__",
) -> QuerySet:
    if period.year is not None:
        results_qs = results_qs.filter(**{f"{game_prefix}played_on__year": period.year})
    if period.month is not None:
        results_qs = results_qs.filter(
            **{f"{game_prefix}played_on__month": period.month}
        )
    return results_qs


def filter_results_by_date_range(
    results_qs: QuerySet,
    *,
    start_date: date,
    end_date: date,
    game_prefix: str = "game__",
) -> QuerySet:
    if start_date > end_date:
        raise ValueError("start_date must be on or before end_date.")
    return results_qs.filter(
        **{
            f"{game_prefix}played_on__gte": start_date,
            f"{game_prefix}played_on__lte": end_date,
        }
    )


def month_label(month: int) -> str:
    return calendar.month_name[month]


def build_leaderboard_query(
    *,
    group_id: str = "",
    game_type_code: str | None = None,
    period: LeaderboardPeriod | None = None,
    game_size: int | None = None,
    extra: dict[str, str] | None = None,
) -> str:
    params: dict[str, str] = {}
    if group_id:
        params["group"] = group_id
    if game_type_code:
        params["game_type_code"] = game_type_code
    if period is not None:
        params.update(period.query_params())
    if game_size is not None:
        params["game_size"] = str(game_size)
    if extra:
        params.update(extra)
    return urlencode(params)


def leaderboard_filter_summary(
    *,
    group_name: str,
    game_type_name: str | None = None,
    period_label: str = "",
    game_size_label: str = "",
) -> str:
    parts = [group_name]
    if game_type_name:
        parts.append(game_type_name)
    if period_label:
        parts.append(period_label)
    if game_size_label:
        parts.append(game_size_label)
    return ", ".join(parts)
