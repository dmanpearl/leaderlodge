from __future__ import annotations

import calendar
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from typing import TYPE_CHECKING
from urllib.parse import urlencode

if TYPE_CHECKING:
    from django.db.models import QuerySet

    from leaderlodge.groups.models import Group

PERIOD_PRESET_TODAY = "today"
PERIOD_PRESET_YESTERDAY = "yesterday"
PERIOD_PRESET_LAST_7_DAYS = "last_7_days"
PERIOD_PRESET_LAST_WEEKEND = "last_weekend"
PERIOD_PRESET_LAST_WEEK = "last_week"
PERIOD_PRESET_CUSTOM = "custom"

PERIOD_PRESET_CHOICES: tuple[tuple[str, str], ...] = (
    (PERIOD_PRESET_TODAY, "Today"),
    (PERIOD_PRESET_YESTERDAY, "Yesterday"),
    (PERIOD_PRESET_LAST_7_DAYS, "Last 7 days"),
    (PERIOD_PRESET_LAST_WEEKEND, "Last weekend"),
    (PERIOD_PRESET_LAST_WEEK, "Last week"),
)

PERIOD_PRESET_CODES = frozenset(code for code, _label in PERIOD_PRESET_CHOICES)


@dataclass(frozen=True)
class LeaderboardPeriod:
    year: int | None = None
    month: int | None = None
    start_date: date | None = None
    end_date: date | None = None
    preset: str | None = None

    @classmethod
    def all_time(cls) -> LeaderboardPeriod:
        return cls()

    @property
    def is_filtered(self) -> bool:
        return (
            self.year is not None
            or self.start_date is not None
            or self.end_date is not None
        )

    @property
    def has_date_range(self) -> bool:
        return self.start_date is not None and self.end_date is not None

    @property
    def apply_bayesian(self) -> bool:
        return not self.is_filtered

    def query_params(self) -> dict[str, str]:
        params: dict[str, str] = {}
        if self.preset and self.preset in PERIOD_PRESET_CODES:
            params["period_preset"] = self.preset
            return params
        if self.has_date_range:
            assert self.start_date is not None and self.end_date is not None
            params["start_date"] = self.start_date.isoformat()
            params["end_date"] = self.end_date.isoformat()
            return params
        if self.year is not None:
            params["year"] = str(self.year)
        if self.month is not None:
            params["month"] = str(self.month)
        return params

    def display_label(self) -> str:
        if self.preset and self.preset in PERIOD_PRESET_CODES:
            for code, label in PERIOD_PRESET_CHOICES:
                if code == self.preset:
                    return label
        if self.has_date_range:
            assert self.start_date is not None and self.end_date is not None
            if self.start_date == self.end_date:
                return _format_day(self.start_date)
            return f"{_format_day(self.start_date)} to {_format_day(self.end_date)}"
        if self.month is not None and self.year is not None:
            return f"{calendar.month_name[self.month]} {self.year}"
        if self.year is not None:
            return str(self.year)
        return ""


def _format_day(value: date) -> str:
    return value.strftime("%b %d, %Y").replace(" 0", " ")


def dates_for_period_preset(
    preset: str,
    *,
    today: date | None = None,
) -> tuple[date, date] | None:
    """Inclusive start/end for a named preset, or None if unknown."""
    if preset not in PERIOD_PRESET_CODES:
        return None
    day = today or date.today()
    if preset == PERIOD_PRESET_TODAY:
        return day, day
    if preset == PERIOD_PRESET_YESTERDAY:
        yesterday = day - timedelta(days=1)
        return yesterday, yesterday
    if preset == PERIOD_PRESET_LAST_7_DAYS:
        return day - timedelta(days=6), day
    if preset == PERIOD_PRESET_LAST_WEEKEND:
        # Most recent Sat-Sun that includes today when today is Sunday;
        # otherwise the previous Saturday-Sunday.
        days_since_sunday = (day.weekday() + 1) % 7
        last_sunday = day - timedelta(days=days_since_sunday)
        last_saturday = last_sunday - timedelta(days=1)
        return last_saturday, last_sunday
    if preset == PERIOD_PRESET_LAST_WEEK:
        # Previous calendar week Monday through Sunday.
        this_monday = day - timedelta(days=day.weekday())
        last_monday = this_monday - timedelta(days=7)
        last_sunday = this_monday - timedelta(days=1)
        return last_monday, last_sunday
    return None


def parse_iso_date(raw: str) -> date | None:
    value = (raw or "").strip()
    if len(value) != 10:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


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
    raw_year: str = "",
    raw_month: str = "",
    raw_preset: str = "",
    raw_start_date: str = "",
    raw_end_date: str = "",
    available_years: list[int],
    months_by_year: dict[int, tuple[int, ...]],
    today: date | None = None,
) -> LeaderboardPeriod:
    """Resolve period from raw inputs.

    Precedence: named preset, then custom date range, then year/month.
    """
    preset = (raw_preset or "").strip()
    if preset in PERIOD_PRESET_CODES:
        bounds = dates_for_period_preset(preset, today=today)
        if bounds is not None:
            start, end = bounds
            return LeaderboardPeriod(start_date=start, end_date=end, preset=preset)

    start = parse_iso_date(raw_start_date)
    end = parse_iso_date(raw_end_date)
    if start is not None and end is not None and start <= end:
        return LeaderboardPeriod(start_date=start, end_date=end)

    year: int | None = None
    if (raw_year or "").strip().isdigit():
        candidate = int(raw_year.strip())
        if candidate in available_years:
            year = candidate

    month: int | None = None
    if year is not None and (raw_month or "").strip().isdigit():
        candidate = int(raw_month.strip())
        if candidate in months_by_year.get(year, ()):
            month = candidate

    return LeaderboardPeriod(year=year, month=month)


def resolve_leaderboard_period_from_mapping(
    params: dict[str, str],
    *,
    available_years: list[int],
    months_by_year: dict[int, tuple[int, ...]],
    today: date | None = None,
) -> LeaderboardPeriod:
    return resolve_leaderboard_period(
        raw_year=params.get("year", ""),
        raw_month=params.get("month", ""),
        raw_preset=params.get("period_preset", ""),
        raw_start_date=params.get("start_date", ""),
        raw_end_date=params.get("end_date", ""),
        available_years=available_years,
        months_by_year=months_by_year,
        today=today,
    )


def period_filter_context(
    *,
    group: Group | None,
    game_type_code: str | None,
    raw_year: str = "",
    raw_month: str = "",
    raw_preset: str = "",
    raw_start_date: str = "",
    raw_end_date: str = "",
    today: date | None = None,
) -> dict:
    if group is None or not game_type_code:
        return {
            "selected_period": LeaderboardPeriod.all_time(),
            "period_year_options": [],
            "period_month_options": [],
            "period_preset_choices": PERIOD_PRESET_CHOICES,
            "period_show_custom_dates": False,
            "period_label": "",
        }

    years, months_by_year = available_leaderboard_periods(group, game_type_code)
    selected_period = resolve_leaderboard_period(
        raw_year=raw_year,
        raw_month=raw_month,
        raw_preset=raw_preset,
        raw_start_date=raw_start_date,
        raw_end_date=raw_end_date,
        available_years=years,
        months_by_year=months_by_year,
        today=today,
    )
    month_options = [
        {"value": month, "label": month_label(month)}
        for month in (
            months_by_year.get(selected_period.year, ())
            if selected_period.year is not None
            else ()
        )
    ]
    show_custom = selected_period.has_date_range and (
        not selected_period.preset or selected_period.preset == PERIOD_PRESET_CUSTOM
    )
    # Keep custom inputs visible when user picked "custom" even before dates apply.
    if (raw_preset or "").strip() == PERIOD_PRESET_CUSTOM:
        show_custom = True
    return {
        "selected_period": selected_period,
        "period_year_options": years,
        "period_month_options": month_options,
        "period_preset_choices": PERIOD_PRESET_CHOICES,
        "period_show_custom_dates": show_custom,
        "period_label": selected_period.display_label(),
    }


def period_filter_context_from_request(
    request,
    *,
    group: Group | None,
    game_type_code: str | None,
) -> dict:
    get = request.GET
    return period_filter_context(
        group=group,
        game_type_code=game_type_code,
        raw_year=get.get("year", "").strip(),
        raw_month=get.get("month", "").strip(),
        raw_preset=get.get("period_preset", "").strip(),
        raw_start_date=get.get("start_date", "").strip(),
        raw_end_date=get.get("end_date", "").strip(),
    )


def filter_results_by_period(
    results_qs: QuerySet,
    period: LeaderboardPeriod,
    *,
    game_prefix: str = "game__",
) -> QuerySet:
    if period.has_date_range:
        assert period.start_date is not None and period.end_date is not None
        return filter_results_by_date_range(
            results_qs,
            start_date=period.start_date,
            end_date=period.end_date,
            game_prefix=game_prefix,
        )
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
    player_type: str = "",
    location_id: int | None = None,
    game_filters=None,
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
    # "people" (Players) is the leaderboard default; omit it from URLs.
    if player_type and player_type != "people":
        params["player_type"] = player_type
    if location_id is not None:
        params["location"] = str(location_id)
    if game_filters is not None:
        params.update(game_filters.query_params())
    if extra:
        params.update(extra)
    return urlencode(params)


def leaderboard_filter_summary(
    *,
    group_name: str,
    game_type_name: str | None = None,
    period_label: str = "",
    game_size_label: str = "",
    player_type_label: str = "",
    location_name: str = "",
    game_filter_labels: list[str] | None = None,
) -> str:
    parts = [group_name]
    if game_type_name:
        parts.append(game_type_name)
    if period_label:
        parts.append(period_label)
    if game_size_label:
        parts.append(game_size_label)
    if player_type_label:
        parts.append(player_type_label)
    if location_name:
        parts.append(location_name)
    if game_filter_labels:
        parts.extend(game_filter_labels)
    return ", ".join(parts)
