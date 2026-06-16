from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from openpyxl import load_workbook

SCOREKEEPER_SHEET = "ScoreKeeper"
DATA_START_ROW = 3
DATE_COL = 0
NANCY_SCORE_COL = 1
DAVID_SCORE_COL = 2
WHERE_COL = 3


@dataclass(frozen=True)
class ScoreKeeperRow:
    row_number: int
    played_on: date
    nancy_score: int
    david_score: int
    location_name: str


def _coerce_date(value) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return None


def _coerce_score(value) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _coerce_location(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def parse_scorekeeper_workbook(path: Path) -> list[ScoreKeeperRow]:
    workbook = load_workbook(path, read_only=True, data_only=True)
    try:
        if SCOREKEEPER_SHEET not in workbook.sheetnames:
            raise ValueError(
                f'Expected a "{SCOREKEEPER_SHEET}" worksheet in {path.name}.'
            )
        worksheet = workbook[SCOREKEEPER_SHEET]
        rows: list[ScoreKeeperRow] = []
        for row_number, values in enumerate(
            worksheet.iter_rows(min_row=DATA_START_ROW, values_only=True),
            start=DATA_START_ROW,
        ):
            if not values:
                continue

            played_on = _coerce_date(values[DATE_COL])
            if played_on is None:
                continue

            nancy_score = _coerce_score(values[NANCY_SCORE_COL])
            david_score = _coerce_score(values[DAVID_SCORE_COL])
            if nancy_score is None or david_score is None:
                continue

            rows.append(
                ScoreKeeperRow(
                    row_number=row_number,
                    played_on=played_on,
                    nancy_score=nancy_score,
                    david_score=david_score,
                    location_name=_coerce_location(
                        values[WHERE_COL] if len(values) > WHERE_COL else None
                    ),
                )
            )
        return rows
    finally:
        workbook.close()
