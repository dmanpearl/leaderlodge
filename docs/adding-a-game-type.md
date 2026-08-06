# Adding a new game type

Checklist for humans and agents. Follow in order. No Django migration is
needed: `Game.game_type_code` is a string keyed by the registry.

For a Gin Rummy / Cornhole-style type (solo sides, no special score modes),
complete **Core**, **Import (Raw Games)**, **Demo seeds**, **Tests**, and
**Docs / SEO**. Skip optional rows unless the type needs them.

## Core (required for Record Game and leaderboards)

1. Register the type in [`leaderlodge/games/registry.py`](../leaderlodge/games/registry.py)
   inside `_load_registry()` as a `GameTypeDefinition`:
   - Required: `code`, `name`, `abbr`, `min_players`, `max_players`,
     `supports_loser`, `score_direction`, `win_target_score`, `icon_filename`
   - Optional: `score_types`, `supports_half_game`, `rank_uses_score_magnitude`,
     `shutout` (`ShutoutConfig`)
2. Add the icon PNG at
   `static/img/game-types/<icon_filename>`
   (resolved by [`leaderlodge/games/game_type_icons.py`](../leaderlodge/games/game_type_icons.py)).
   If `shutout=` is set, add that shutout icon in the same directory.
3. Prefer shared scoring: [`leaderlodge/games/scoring.py`](../leaderlodge/games/scoring.py)
   and validators already assign W/L/T and placement from registry flags.
   Add custom logic only when those rules are not enough.
4. Optional capability wiring in
   [`leaderlodge/games/features.py`](../leaderlodge/games/features.py)
   (`GAME_FEATURES`) for score-type / double / half filters used by lists and Ask.

Record Game forms and About **Game Types** list the registry dynamically.
You do not hardcode the new code into form choice lists.

## Import path (required for `import_games` and demo seeds)

Wire the code in
[`leaderlodge/games/importing/service.py`](../leaderlodge/games/importing/service.py)
via `import_games_file()`:

| Format | When to use | How to wire |
|--------|-------------|-------------|
| ScoreKeeper | Fixed two player columns (Dominos, Backgammon) | Add `code` to `SCOREKEEPER_GAME_TYPES` |
| Raw Games | Multi-player columns, blank = did not play | Add `code` to `RAW_GAMES_GAME_TYPES` |
| Pickleball-style | Rotating sides / teams / score type | New branch + `importing/pickleball.py` pattern |

Without an importer, recording still works, but `import_games` and demo
seed loading will fail for that type.

Spreadsheet layouts: [importing.md](./importing.md).

## Demo seeds (required for full Demo / `setup_demo`)

1. Prefer the generator
   [`tools/generate_new_game_demo_seeds.py`](../tools/generate_new_game_demo_seeds.py):
   - Add `generate_<code>(rng)` that writes
     `data/seeds/<code>/<code>_demo_YYYY-MM-DD.xlsx`
   - Call it from `main()`
   - Use `Where` names from
     [`leaderlodge/groups/demo_seed_venues_data.py`](../leaderlodge/groups/demo_seed_venues_data.py)
     so Map pins get coordinates on import (about 75% US venues). Only extend
     that catalog if you need new venue strings.
   - Per sport, randomize game count (50-80) and year span (3-6) via
     `_sport_params` (or the same pattern).
2. Register the path in
   [`leaderlodge/groups/demo.py`](../leaderlodge/groups/demo.py)
   `DEMO_SEED_IMPORTS`.
3. Run:

```bash
source venv/bin/activate
python tools/generate_new_game_demo_seeds.py
python manage.py setup_demo --dry-run   # confirm the new file is listed
python manage.py setup_demo             # import when ready
```

`setup_demo` fails if any `DEMO_SEED_IMPORTS` file is missing. Re-import is
idempotent by `(import_source, import_row_key)`.

## Tests

1. Parametrize
   `tests/test_import_games.py::test_import_committed_generated_demo_seeds`
   with `("<code>", "data/seeds/<code>/...xlsx")` when you add a generated demo.
2. Optional: abbr / lock coverage in `tests/test_game_type_lock.py`.
3. Optional: dedicated rule tests under `leaderlodge/games/types/` (legacy;
   many newer types skip this).

## Docs and SEO (manual; not driven by the registry)

Update hard-coded game name lists and counts:

- [`docs/features.md`](./features.md) supported-games list
- [`docs/importing.md`](./importing.md) format notes + Demo path list
- [`docs/setup.md`](./setup.md) / [`README.md`](../README.md) if they state a count
- [`templates/core/about.html`](../templates/core/about.html): meta, OG/Twitter,
  JSON-LD `featureList`, and any prose that lists games by name
- [`templates/core/about_insights.html`](../templates/core/about_insights.html):
  meta / OG / Twitter

About's on-page **Game Types** loop does not need a code change.

If rank or Ask behavior is special, also update
[`docs/rank-scoring.md`](./rank-scoring.md) and/or
[`docs/ask-the-lodge-capabilities.md`](./ask-the-lodge-capabilities.md).

## Quick minimum (like Gin Rummy)

1. `registry.py` + icon
2. `RAW_GAMES_GAME_TYPES`
3. `generate_<code>` + `DEMO_SEED_IMPORTS` + regenerate seeds
4. Import test parametrize
5. Docs + About meta lists

## Related docs

- [Importing game history](./importing.md) (spreadsheet formats, demo seeds)
- [Features](./features.md) (product list)
- [Architecture](./architecture.md) (apps and ranking)
- [Local setup](./setup.md) (`setup_demo`)
