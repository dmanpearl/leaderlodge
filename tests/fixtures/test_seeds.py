"""Paths and helpers for minimal committed test seed spreadsheets."""

from __future__ import annotations

from pathlib import Path

TEST_SEED_IMPORTS: tuple[tuple[str, str], ...] = (
    ("dominos", "dominos_test.xlsx"),
    ("backgammon", "backgammon_test.xlsx"),
    ("progressiverummy", "progressiverummy_test.xlsx"),
    ("mahjongg", "mahjongg_test.xlsx"),
)

# parsed / created / skipped for each committed test seed file
EXPECTED_IMPORT_SUMMARIES: dict[str, tuple[int, int, int]] = {
    "dominos": (4, 4, 0),
    "backgammon": (4, 4, 0),
    "progressiverummy": (5, 5, 0),
    "mahjongg": (4, 3, 1),
}

# Games persisted after a successful import (created count only)
EXPECTED_GAME_COUNTS: dict[str, int] = {
    game_type: created for game_type, (_, created, _) in EXPECTED_IMPORT_SUMMARIES.items()
}


def committed_test_seeds_dir() -> Path:
    return Path(__file__).resolve().parent / "seeds"


def committed_test_seed_paths(base_dir: Path) -> list[tuple[str, Path]]:
    seeds = committed_test_seeds_dir()
    return [(game_type, seeds / filename) for game_type, filename in TEST_SEED_IMPORTS]


def all_committed_test_seeds_present() -> bool:
    return all(path.is_file() for _, path in committed_test_seed_paths(Path(".")))
