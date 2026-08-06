# Management commands

Project-owned Django management commands live under
`leaderlodge/*/management/commands/`. This page is the inventory and short
usage guide. For full flag lists, run:

```bash
python manage.py help
python manage.py <command> --help
```

Against production:

```bash
railway run python manage.py <command> ...
```

Topic docs still cover deep workflows (imports, Places, email). Link here for
the full list. A sync test fails CI if a new command is added without a
matching `###` heading below.

---

## Accounts

### find_fake_accounts

Identify likely fake / spam user accounts (random usernames, bot-generated
names, little or no engagement). Default is report-only across active and
inactive users.

```bash
python manage.py find_fake_accounts
python manage.py find_fake_accounts --active-only
python manage.py find_fake_accounts --deactivate
python manage.py find_fake_accounts --delete
```

| Flag | Purpose |
|------|---------|
| `--active-only` | Only accounts that can still log in |
| `--deactivate` | Set `is_active=False` and log an AuthEvent |
| `--delete` | Hard-delete candidates with no PROTECT relations |
| `--min-score` | Minimum spam score (default 3) |
| `--username` | Limit to one username (repeatable) |
| `--include-engaged` | Do not exclude users with memberships/games |

Prefer `--deactivate` for safety; use `--delete` only when the report marks
rows `deletable`.

### send_sample_email

Render welcome or password-reset email templates for development validation.
See [Preview transactional emails](setup.md#preview-transactional-emails).

```bash
python manage.py send_sample_email --type welcome --user YOUR_USERNAME --print-only
python manage.py send_sample_email --type password-reset --user YOUR_USERNAME
```

| Flag | Purpose |
|------|---------|
| `--type` | `welcome` or `password-reset` (required) |
| `--user` | Username for template context (required) |
| `--to` | Override recipient (default: user email) |
| `--site-url` | Base URL for links (default `http://127.0.0.1:8000`) |
| `--print-only` | Print subject/body; do not send |

---

## Core

### setup_site_settings

Create or update the site settings singleton (admin notify email and
notification toggles). See [Site settings](setup.md#site-settings-admin-notifications).

```bash
python manage.py setup_site_settings --email=you@example.com
```

`--email` is required. Re-running is safe.

---

## Games

### import_games

Import games from a ScoreKeeper spreadsheet (`.xlsx`). Idempotent by
spreadsheet row. See [Importing game history](importing.md). New game types:
[Adding a new game type](adding-a-game-type.md).

```bash
python manage.py import_games \
  -g manpearl \
  --game-type dominos \
  data/seeds/dominos/dominos_seed_2026-07-16.xlsx
```

| Flag | Purpose |
|------|---------|
| `-g` / `--group` | Target group name or pk (required) |
| `--game-type` | Game type code (required) |
| `--recorded-by` | Recorder username (default: group owner) |
| `--dry-run` | Validate without writing |

### change_game_score

Change one participant score (optional location), recalculate results, and
write audit log entries.

```bash
python manage.py change_game_score \
  --game 123 \
  --player "Nancy" \
  --score 150 \
  --changed-by YOUR_USERNAME \
  --notes "Corrected typo from paper scorecard" \
  --dry-run
```

### change_game_location

Change a game's location and write an audit log entry.

```bash
python manage.py change_game_location \
  --game 123 \
  --location "Cafe 50s" \
  --changed-by YOUR_USERNAME \
  --notes "Player confirmed venue" \
  --dry-run
```

Pass an empty `--location` value to clear the location.

### recalculate_game_results

Recalculate participant results, placements, and double weight from stored
scores using current registry rules.

```bash
python manage.py recalculate_game_results --game 123 \
  --changed-by YOUR_USERNAME \
  --notes "After scoring rule tweak"
python manage.py recalculate_game_results --game-type dominos -g manpearl \
  --changed-by YOUR_USERNAME \
  --notes "Backfill placements" \
  --dry-run
```

Use exactly one scope: `--game`, `--game-type` (optional `-g`), or `--all`.

---

## Groups

### setup_demo

Create or update the public Demo group (`is_demo=True`) and import all bundled
demo seed spreadsheets. See [Demo group seeds](importing.md#demo-group-seeds).
Adding another demo type: [Adding a new game type](adding-a-game-type.md).

```bash
python manage.py setup_demo
python manage.py setup_demo --owner YOUR_USERNAME --dry-run
```

### promote_games

Promote games from a source group (default `manpearl`) into Demo with player
and location anonymization. Idempotent; use `--purge` for a clean redo.

```bash
python manage.py promote_games --dry-run
python manage.py promote_games --game-type dominos
python manage.py promote_games --purge
```

| Flag | Purpose |
|------|---------|
| `--source-group` | Source group (default `manpearl`) |
| `--dest-group` | Destination (default `Demo`) |
| `--game-type` | Limit to one game type |
| `--recorded-by` | Recorder username (default: dest owner) |
| `--purge` | Delete previously promoted dest games first |
| `--dry-run` | Report without writing |

### backfill_location_places

Interactively geocode ungeocoded locations via Places text search
(accept/reject per row). See
[Interactive CLI backfill](google-places.md#interactive-cli-backfill-optional).

```bash
python manage.py backfill_location_places \
  --group manpearl \
  --skip-file /tmp/manpearl_place_skips.json \
  --limit 40
```

Requires `GOOGLE_PLACES_SERVER_API_KEY`.

### sync_group_locations

Copy location names and geo from a source group onto matching locations in a
destination group. Does not create missing locations or share libraries.

```bash
python manage.py sync_group_locations --src manpearl --dst Demo --dry-run
python manage.py sync_group_locations --src manpearl --dst Demo
```
