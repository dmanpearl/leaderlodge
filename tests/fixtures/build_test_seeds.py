"""Generate minimal test seed spreadsheets under tests/fixtures/seeds/."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from openpyxl import Workbook

SEEDS_DIR = Path(__file__).resolve().parent / "seeds"


def _write_scorekeeper(
    path: Path,
    rows: list[tuple],
    *,
    headers: tuple[str, ...],
) -> None:
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "ScoreKeeper"
    worksheet.append(headers)
    worksheet.append(("Totals", 0, 0, None, 0, 0, None))
    for row in rows:
        worksheet.append(row)
    workbook.save(path)


def _write_raw_games(path: Path, headers: tuple[str, ...], rows: list[tuple]) -> None:
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Raw Games"
    worksheet.append(headers)
    for row in rows:
        worksheet.append(row)
    workbook.save(path)


def build_all() -> None:
    SEEDS_DIR.mkdir(parents=True, exist_ok=True)

    _write_scorekeeper(
        SEEDS_DIR / "dominos_test.xlsx",
        headers=("Date", "Nancy", "David", "Where", "Nancy", "David", "Diff"),
        rows=[
            (datetime(2026, 3, 8), 25, 30, "Sally"),
            (datetime(2026, 3, 9), 30, 25, None),
            (datetime(2026, 3, 10), 28, 28, "Lodge"),
            (datetime(2026, 3, 11), 35, 20, None),
        ],
    )

    _write_scorekeeper(
        SEEDS_DIR / "backgammon_test.xlsx",
        headers=("Date", "Carter", "Elena", "Where", "Carter", "Elena", "Diff"),
        rows=[
            (datetime(2026, 4, 1), 1, 0, "Home"),
            (datetime(2026, 4, 2), 0, 1, None),
            (datetime(2026, 4, 3), 2, 0, "Lodge"),
            (datetime(2026, 4, 4), 0, 2, None),
        ],
    )

    pr_headers = (
        "Date",
        "Where",
        "Half",
        "aa",
        "Nancy",
        "David",
        "Pat",
        "Min",
        "Max",
        "Winner",
        "Loser",
        "Players",
    )
    _write_raw_games(
        SEEDS_DIR / "progressiverummy_test.xlsx",
        pr_headers,
        [
            (
                datetime(2026, 3, 8),
                "Sally",
                "Yes",
                "skip",
                10,
                20,
                30,
                10,
                30,
                "Nancy",
                "Pat",
                3,
            ),
            (
                datetime(2026, 3, 9),
                "<?>",
                None,
                None,
                5,
                15,
                25,
                5,
                25,
                "Nancy",
                "Pat",
                3,
            ),
            ("<?>", "Kitchen", None, None, 8, 18, 28, 8, 28, "Nancy", "Pat", 3),
            (
                datetime(2026, 3, 10),
                "Lodge",
                None,
                None,
                12,
                14,
                16,
                12,
                16,
                "Nancy",
                "Pat",
                3,
            ),
            (
                datetime(2026, 3, 11),
                "",
                "Yes",
                None,
                6,
                8,
                10,
                6,
                10,
                "Nancy",
                "Pat",
                3,
            ),
        ],
    )

    mj_headers = (
        "Date",
        "Where",
        "Half",
        "aa",
        "Carter",
        "Elena",
        "Lily",
        "Owen",
    )
    _write_raw_games(
        SEEDS_DIR / "mahjongg_test.xlsx",
        mj_headers,
        [
            (datetime(2026, 3, 8), "Lodge", None, None, 25, 0, 0, 0),
            (datetime(2026, 3, 9), "Club", None, None, 0, 30, 10, 5),
            (datetime(2026, 3, 10), "Treehouse", None, None, 10, 20, None, None),
            (datetime(2026, 3, 11), "Patio", None, None, 5, 15, 25, 10),
        ],
    )


if __name__ == "__main__":
    build_all()
    print(f"Wrote test seeds to {SEEDS_DIR}")
