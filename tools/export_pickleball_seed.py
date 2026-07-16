#!/usr/bin/env python
"""Export Pickleball games from a group into a Raw Games style seed workbook."""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date, datetime
from pathlib import Path

import django

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "leaderlodge.settings.local")
django.setup()

from openpyxl import Workbook

from leaderlodge.games.models import Game
from leaderlodge.games.registry import ScoreType
from leaderlodge.groups.models import Group
from leaderlodge.groups.teams import team_display_name, team_member_players

RAW_GAMES_SHEET = "Raw Games"
METADATA_HEADERS = ("Min", "Max", "Winner", "Loser", "Players")


def side_label(player) -> str:
    if player.is_team:
        return team_display_name(team_member_players(player))
    return player.display_label


def collect_games(*, group: Group) -> list[Game]:
    return list(
        Game.objects.filter(group=group, game_type_code="pickleball")
        .prefetch_related(
            "participant_results__player__team_members__member__linked_user",
            "participant_results__player",
            "location",
        )
        .order_by("played_on", "pk")
    )


def build_rows(games: list[Game]) -> tuple[list[str], list[list[object]]]:
    side_labels: set[str] = set()
    game_rows: list[tuple[date, str, str, dict[str, int]]] = []

    for game in games:
        scores_by_side: dict[str, int] = {}
        for result in game.participant_results.order_by("placement", "pk"):
            label = side_label(result.player)
            side_labels.add(label)
            scores_by_side[label] = result.score

        score_type = ""
        if game.score_type == ScoreType.RALLY.value:
            score_type = "Rally"

        location_name = game.location.name if game.location else ""
        game_rows.append((game.played_on, location_name, score_type, scores_by_side))

    ordered_sides = sorted(side_labels, key=lambda value: value.lower())
    headers = ["Date", "Where", "Score type", "aa", *ordered_sides, *METADATA_HEADERS]

    rows: list[list[object]] = []
    for played_on, location_name, score_type, scores_by_side in game_rows:
        row: list[object] = [played_on, location_name, score_type or None, None]
        for label in ordered_sides:
            row.append(scores_by_side.get(label))
        row.extend([None] * len(METADATA_HEADERS))
        rows.append(row)

    return headers, rows


def write_workbook(*, path: Path, headers: list[str], rows: list[list[object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = RAW_GAMES_SHEET
    worksheet.append(headers)
    for row in rows:
        worksheet.append(row)
    workbook.save(path)


def resolve_group(identifier: str) -> Group:
    if identifier.isdigit():
        group = Group.objects.filter(pk=int(identifier)).first()
        if group is not None:
            return group
    group = Group.objects.filter(name__iexact=identifier).first()
    if group is not None:
        return group
    group = Group.objects.filter(is_demo=True).first()
    if group is not None:
        return group
    raise SystemExit(f"Group not found: {identifier}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--group",
        default="Demo",
        help="Group name or primary key (default: Demo)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "data/seeds/pickleball/pickleball_demo_2026-07-16.xlsx",
        help="Output .xlsx path",
    )
    args = parser.parse_args()

    group = resolve_group(args.group)
    games = collect_games(group=group)
    if not games:
        raise SystemExit(f"No Pickleball games found for group {group.name}.")

    headers, rows = build_rows(games)
    write_workbook(path=args.output, headers=headers, rows=rows)
    print(f"Wrote {len(rows)} games to {args.output} (group: {group.name})")


if __name__ == "__main__":
    main()
