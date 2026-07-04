# Importing game history

LeaderLodge can import historical games from Excel **ScoreKeeper** workbooks. Imports are idempotent: re-running the same file skips rows that were already imported.

## Seed file layout

Store versioned seed files under `data/seeds/<game-type>/`:

```text
data/seeds/dominos/dominos_seed_2026-06-16.xlsx
data/seeds/backgammon/backgammon_seed_2026-06-16.xlsx
data/seeds/progressiverummy/progressiverummy_seed_2026-06-16.xlsx
data/seeds/pickleball/pickleball_demo_2026-07-04.xlsx
```

Date-stamped filenames act as lightweight version control for binary spreadsheets. You can keep older exports alongside newer ones; each file is identified separately during import.

Progressive Rummy, Mah Jongg, and Pickleball use a **Raw Games** worksheet in a separate seed format (see below).

## Spreadsheet format (dominos & backgammon)

Both games use a worksheet named **ScoreKeeper**:

| Row | Purpose |
|-----|---------|
| 1 | Column headers |
| 2 | Totals row (ignored) |
| 3+ | One game per row |

Columns used for import:

| Column | Field |
|--------|-------|
| A | Date played |
| B | First player's score (header row is the player name) |
| C | Second player's score (header row is the player name) |
| D | Location (`Where`), optional |

Running totals and win-count columns are ignored. Rows without a valid date or both scores are skipped.

Player names come from the **column B and C headers** on row 1 (not hardcoded).

## Import command

The spreadsheet path is **required**. There is no default file path.

```bash
source venv/bin/activate

python manage.py import_games \
  --group "Family" \
  --game-type dominos \
  data/seeds/dominos/dominos_seed_2026-06-16.xlsx

python manage.py import_games \
  -g 3 \
  --game-type backgammon \
  data/seeds/backgammon/backgammon_seed_2026-06-16.xlsx

python manage.py import_games \
  --group "Family" \
  --game-type progressiverummy \
  data/seeds/progressiverummy/progressiverummy_seed_2026-06-16.xlsx

python manage.py import_games \
  --group Demo \
  --game-type pickleball \
  data/seeds/pickleball/pickleball_demo_2026-07-04.xlsx
```

### Options

| Option | Description |
|--------|-------------|
| `spreadsheet` | Path to the `.xlsx` file (positional, required) |
| `-g`, `--group` | Target group name or primary key (required) |
| `--game-type` | Game type code: `dominos`, `backgammon`, `progressiverummy`, `pickleball`, etc. (required) |
| `--recorded-by` | Username stored as recorder (default: group owner) |
| `--dry-run` | Parse and validate without writing to the database |

Re-importing the same file is safe. Each row is keyed by `(group, import_source, import_row_key)` where `import_source` is the spreadsheet filename without extension and `import_row_key` is the Excel row number.

You can import any compatible file from anywhere:

```bash
python manage.py import_games -g "Family" --game-type dominos ~/Downloads/my_scores.xlsx
```

## Player mapping (ScoreKeeper games)

Dominos and backgammon read player names from the **column B and C headers** on row 1.

For each name, the importer looks for an existing active player in the target group:

1. `linked_user.username` (case-insensitive)
2. `linked_user.first_name` (case-insensitive)
3. `display_name` (case-insensitive)

If no match is found, a guest player is created with that display name.

## Locations

Non-empty values in the **Where** column are resolved through the group's location library. LeaderLodge merges similar names automatically using the same fuzzy logic as the location autocomplete:

- Accent-insensitive matching (`Zinqué` → `Zinque`)
- Prefix and contains matching (`Zinque` → `Zinque, Venice`)
- Punctuation ignored for matching (`Zinque, Venice` → `Zinque Venice`)

Exact normalized matches take priority. When several locations score similarly, no automatic merge is performed.

## Display names in the app

Linked users are shown using this format:

1. First and last name present → `First L.` (first name + last initial + dot)
2. First name only → first name
3. Otherwise → username

Guest players (no linked user) use their stored `display_name`.

## Spreadsheet format (Progressive Rummy)

Store seed files under `data/seeds/progressiverummy/`. Only the **Raw Games** worksheet is imported; other sheets (Leaders, Stats, etc.) are ignored.

| Column | Field |
|--------|-------|
| A | Date played (`<?>` ignored; undated games sort before the earliest dated game) |
| B | Location (`Where`; `<?>` ignored) |
| C | Half game (`Yes` marks a half game) |
| D | Skipped (`aa` placeholder column) |
| E–AH | Player names with scores for that game |
| Min, Max, Winner, Loser, Players | Skipped during import (reserved for future algorithm tests) |

Rows without at least one player score are skipped. Rows with fewer than 2 or more than 10 scored players are skipped (Progressive Rummy player limits). Win/loss/tie results are computed from scores using Progressive Rummy rules (low score wins; explicit loser when scores differ).

Half games are stored on the `Game` as `half_weight=2` (normal games use `1`), mirroring how dominos doubles use `double_weight=2`. Leaderboard standings count half games at 0.5× (`double_weight / half_weight`).

### Player mapping (Progressive Rummy)

Each player column header is a display name. For each name, the importer uses the same lookup order as dominos/backgammon:

1. `linked_user.username` (case-insensitive)
2. `linked_user.first_name` (case-insensitive)
3. `display_name` (case-insensitive)

If no match is found, a guest player is created with that display name.

## Spreadsheet format (Mah Jongg)

Mah Jongg uses the same **Raw Games** worksheet layout as Progressive Rummy (see above). Store seed files under `data/seeds/mahjongg/`.

Differences during import:

- **Half** column is ignored (Mah Jongg has no half games).
- Rows must have **3 to 4** scored players (Mah Jongg player limits).
- Win/loss/tie results use Mah Jongg rules (high score wins).

Blank player cells mean that player did not participate in the game. A score of `0` is valid (for example, a wall game).

## Spreadsheet format (Pickleball)

Store seed files under `data/seeds/pickleball/`. Uses the **Raw Games** worksheet with side columns that can rotate from row to row (unlike ScoreKeeper, which fixes two player columns for the whole file).

| Column | Field |
|--------|-------|
| A | Date played |
| B | Location (`Where`) |
| C | Score type (`Rally` or blank for Traditional) |
| D | Skipped (`aa` placeholder column) |
| E+ | Side labels with scores for that game |

Each **side** is one column header:

- Solo: `Lucas`, `Aurora`
- Team: `Harper+Owen`, `Elena+Lucy` (member display names joined with `+`)

Only the sides that played receive scores on each row. Rows with **2 to 3** scored sides are imported (Pickleball player limits). Rows where the same person would appear on more than one side are skipped.

`Rally` in the **Score type** column is stored on the game. A blank cell means Traditional.

Win/loss/tie results use Pickleball rules (high score wins). Team sides create or reuse team roster entries the same way as **Record Game**.

### Export Pickleball seeds from a group

To build a spreadsheet from games already in the database:

```bash
python tools/export_pickleball_seed.py --group Demo \
  --output data/seeds/pickleball/pickleball_demo_2026-07-04.xlsx
```

## Demo group seeds

Bundled demo spreadsheets use fictional player names and live in the repo under `data/seeds/`:

```text
data/seeds/dominos/dominos_demo_2026-06-22.xlsx
data/seeds/backgammon/backgammon_demo_2026-06-22.xlsx
data/seeds/progressiverummy/progressiverummy_demo_2026-06-22.xlsx
data/seeds/mahjongg/mahjongg_demo_2026-06-22.xlsx
data/seeds/pickleball/pickleball_demo_2026-07-04.xlsx
```

### One-command demo setup

`setup_demo` creates the **Demo** group (if needed), sets **`is_demo=True`**, and imports all five files above. Re-running is safe: existing games from the same spreadsheet rows are skipped.

```bash
source venv/bin/activate

# After migrate and createsuperuser:
python manage.py setup_demo
```

| Option | Description |
|--------|-------------|
| `--owner USERNAME` | Group owner and import recorder (default: first superuser) |
| `--dry-run` | Show planned actions without writing to the database |

On Railway:

```bash
railway run python manage.py setup_demo
```

Or pass a specific owner:

```bash
railway run python manage.py setup_demo --owner yourusername
```

Migration `0004_group_is_demo` also sets `is_demo=True` on an existing group named **Demo** when you run `migrate`. Use `setup_demo` on production to create the group, set the flag, and load seed data in one step — no admin panel required.

To import demo seeds manually instead:

```bash
python manage.py import_games --group Demo --game-type dominos \
  data/seeds/dominos/dominos_demo_2026-06-22.xlsx

python manage.py import_games --group Demo --game-type backgammon \
  data/seeds/backgammon/backgammon_demo_2026-06-22.xlsx

python manage.py import_games --group Demo --game-type progressiverummy \
  data/seeds/progressiverummy/progressiverummy_demo_2026-06-22.xlsx

python manage.py import_games --group Demo --game-type mahjongg \
  data/seeds/mahjongg/mahjongg_demo_2026-06-22.xlsx

python manage.py import_games --group Demo --game-type pickleball \
  data/seeds/pickleball/pickleball_demo_2026-07-04.xlsx
```

## Dependencies

Spreadsheet import requires `openpyxl`, included in `requirements.txt`.
