"""Demo group name and bundled seed spreadsheets (paths relative to project root)."""

from pathlib import Path

DEMO_GROUP_NAME = "Demo"
DEMO_GROUP_DESCRIPTION = (
    "Example group with real game data. Login and use '+ Create Group' to add your "
    "own and start logging game scores."
)
GUEST_LOGIN_PROMPT = "Login to create your own Group of Players and start scoring"
GUEST_DEMO_PAGE_NOTICE = (
    "You're browsing sample data. Sign up or login, create a group with "
    "+ Create Group, then record games to start scoring."
)

DEMO_SEED_IMPORTS: tuple[tuple[str, str], ...] = (
    ("dominos", "data/seeds/dominos/dominos_demo_2026-07-16.xlsx"),
    ("backgammon", "data/seeds/backgammon/backgammon_demo_2026-07-16.xlsx"),
    (
        "progressiverummy",
        "data/seeds/progressiverummy/progressiverummy_demo_2026-07-16.xlsx",
    ),
    ("mahjongg", "data/seeds/mahjongg/mahjongg_demo_2026-07-16.xlsx"),
    ("pickleball", "data/seeds/pickleball/pickleball_demo_2026-07-16.xlsx"),
)


def demo_seed_paths(base_dir: Path) -> list[tuple[str, Path]]:
    return [
        (game_type, base_dir / relative_path)
        for game_type, relative_path in DEMO_SEED_IMPORTS
    ]
