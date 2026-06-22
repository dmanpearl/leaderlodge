# Local development

See [README.md](../README.md) for first-time bootstrap (venv, `.env`, install, run).

## Prerequisites

- Python 3.11+

## Environment variables

```bash
cp .env.example .env
```

Set `DJANGO_SECRET_KEY` in `.env` before running any Django command. See README.md for key generation.

## Daily workflow

```bash
cd ~/pixelmonks/leaderlodge
source venv/bin/activate
python manage.py runserver
```

On Windows: `venv\Scripts\activate`

## First run

```bash
source venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
# edit .env — set DJANGO_SECRET_KEY
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Open http://127.0.0.1:8000/

## Settings

| Module | Use |
|--------|-----|
| `leaderlodge.settings.local` | Local dev (SQLite, default via `manage.py`) |
| `leaderlodge.settings.production` | Railway / PostgreSQL |

Set `DJANGO_SETTINGS_MODULE=leaderlodge.settings.production` in Railway only. Local dev does not need this variable.

With no `DATABASE_URL`, local settings use SQLite.

For `railway run` against production PostgreSQL, database URL resolution is automatic (see `leaderlodge/railway_db.py`). Optionally override with the public URL in `.env` as `DATABASE_URL`.

## Tests

```bash
source venv/bin/activate
pytest
```

Tests use `leaderlodge.settings.test` (see `pytest.ini`). You do not need a `.env` file to run pytest, but you need one for `manage.py` commands.

Pytest uses a dedicated SQLite file, `test_db.sqlite3` (not `db.sqlite3`), and reuses it between runs (`--reuse-db` in `pytest.ini`) so repeat runs stay fast.

**After you change models or add migrations**, rebuild the test database once:

```bash
pytest --create-db
```

Or delete the file and run pytest normally:

```bash
rm test_db.sqlite3 && pytest
```

Both commands run the same tests; `--create-db` only forces a fresh schema. Use it when migrations change or tests fail in ways that smell like a stale DB.

## Importing historical games

See [Importing game history](importing.md) for seed file layout, player mapping, and the `import_games` management command.

Quick example:

```bash
python manage.py import_games \
  --group "manpearl" \
  --game-type dominos \
  data/seeds/dominos/dominos_seed_2026-06-16.xlsx
```

## Demo group (public read-only)

Anonymous visitors can browse the **Demo** group when `DEMO_MODE_ENABLED` is true (default). See [Importing game history — Demo group seeds](importing.md#demo-group-seeds) for spreadsheet paths and formats.

After `migrate` and `createsuperuser`:

```bash
python manage.py setup_demo
```

This creates the **Demo** group, sets **`is_demo=True`**, and imports all four bundled `*_demo_2026-06-22.xlsx` seed files. Re-running is idempotent.

Log out and open http://127.0.0.1:8000/ to confirm the demo landing page. Set `DEMO_MODE_ENABLED=false` in `.env` or Railway variables to disable public demo browsing.

### Railway production

After deploy (migrate runs automatically via `railway.json`):

```bash
railway link
railway run python manage.py createsuperuser   # first time only
railway run python manage.py setup_demo
```

Use `--owner USERNAME` if you have multiple superusers and want a specific group owner. No Django admin step is required to set **Is demo**.
