"""Hall of Fame grid: period leaders per game type for a group."""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from typing import TYPE_CHECKING
from urllib.parse import urlencode

from leaderlodge.games.registry import get_game_type
from leaderlodge.leaderboards.period import LeaderboardPeriod, build_leaderboard_query
from leaderlodge.leaderboards.service import get_player_rankings

if TYPE_CHECKING:
    from leaderlodge.groups.models import Group

GRANULARITY_YEAR = "year"
GRANULARITY_MONTH = "month"
GRANULARITIES = (GRANULARITY_YEAR, GRANULARITY_MONTH)


@dataclass(frozen=True)
class HallOfFameColumn:
    code: str
    name: str


@dataclass(frozen=True)
class HallOfFameCell:
    player_label: str
    player_id: int | None
    rank_score: float | None
    game_type_code: str
    detail_query: str


@dataclass(frozen=True)
class HallOfFameRow:
    label: str
    period: LeaderboardPeriod
    cells: tuple[HallOfFameCell, ...]


@dataclass(frozen=True)
class HallOfFameGrid:
    columns: tuple[HallOfFameColumn, ...]
    rows: tuple[HallOfFameRow, ...]


def resolve_hall_of_fame_granularity(raw: str) -> str:
    if raw == GRANULARITY_MONTH:
        return GRANULARITY_MONTH
    return GRANULARITY_YEAR


def granularity_label(granularity: str) -> str:
    return "Months" if granularity == GRANULARITY_MONTH else "Years"


def hall_of_fame_filter_summary(*, group_name: str, granularity: str) -> str:
    return f"{group_name}, {granularity_label(granularity)}"


def build_hall_of_fame_query(
    *,
    group_id: str = "",
    granularity: str = GRANULARITY_YEAR,
    player_type: str = "",
) -> str:
    params: dict[str, str] = {}
    if group_id:
        params["group"] = group_id
    if granularity != GRANULARITY_YEAR:
        params["granularity"] = granularity
    # "people" (Players) is the default; omit it from URLs.
    if player_type and player_type != "people":
        params["player_type"] = player_type
    return urlencode(params)


def _game_type_codes_for_group(group: Group) -> list[str]:
    from leaderlodge.games.models import Game

    return list(
        Game.objects.filter(group=group)
        .values_list("game_type_code", flat=True)
        .distinct()
        .order_by("game_type_code")
    )


def _period_rows(group: Group, *, granularity: str) -> list[LeaderboardPeriod]:
    from leaderlodge.games.models import Game

    dates = list(Game.objects.filter(group=group).values_list("played_on", flat=True))
    if not dates:
        return []

    if granularity == GRANULARITY_MONTH:
        seen: set[tuple[int, int]] = set()
        for played_on in dates:
            seen.add((played_on.year, played_on.month))
        ordered = sorted(seen, reverse=True)
        return [LeaderboardPeriod(year=year, month=month) for year, month in ordered]

    years = sorted({played_on.year for played_on in dates}, reverse=True)
    return [LeaderboardPeriod(year=year) for year in years]


def _period_row_label(period: LeaderboardPeriod, *, granularity: str) -> str:
    if granularity == GRANULARITY_MONTH and period.month is not None and period.year:
        return f"{calendar.month_abbr[period.month]}, {period.year}"
    if period.year is not None:
        return str(period.year)
    return ""


def _leader_cell(
    group: Group,
    *,
    game_type_code: str,
    period: LeaderboardPeriod,
    player_type: str = "",
    label_map: dict[int, str] | None = None,
) -> HallOfFameCell:
    rankings = get_player_rankings(
        group,
        game_type_code=game_type_code,
        period=period,
        player_type=player_type,
    )
    if not rankings:
        return HallOfFameCell(
            player_label="",
            player_id=None,
            rank_score=None,
            game_type_code=game_type_code,
            detail_query="",
        )

    leader = rankings[0]
    player_label = (
        label_map.get(leader.player.pk, leader.player.display_label)
        if label_map
        else leader.player.display_label
    )
    detail_query = ""
    if leader.player.pk:
        detail_query = build_leaderboard_query(
            group_id=str(group.pk),
            game_type_code=game_type_code,
            period=period,
            extra={"player": str(leader.player.pk)},
        )
    return HallOfFameCell(
        player_label=player_label,
        player_id=leader.player.pk,
        rank_score=leader.rank_score,
        game_type_code=game_type_code,
        detail_query=detail_query,
    )


def build_hall_of_fame_grid(
    group: Group,
    *,
    granularity: str,
    player_type: str = "",
    label_map: dict[int, str] | None = None,
    allowed_game_type_codes: list[str] | None = None,
) -> HallOfFameGrid:
    codes = _game_type_codes_for_group(group)
    if allowed_game_type_codes is not None:
        allowed = frozenset(allowed_game_type_codes)
        codes = [code for code in codes if code in allowed]
    columns = tuple(
        HallOfFameColumn(code=code, name=get_game_type(code).name) for code in codes
    )
    periods = _period_rows(group, granularity=granularity)
    rows: list[HallOfFameRow] = []
    for period in periods:
        cells = tuple(
            _leader_cell(
                group,
                game_type_code=column.code,
                period=period,
                player_type=player_type,
                label_map=label_map,
            )
            for column in columns
        )
        rows.append(
            HallOfFameRow(
                label=_period_row_label(period, granularity=granularity),
                period=period,
                cells=cells,
            )
        )
    return HallOfFameGrid(columns=columns, rows=tuple(rows))
