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
pip install -r requirements/local.txt
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

With no `DATABASE_URL`, local settings use SQLite. To run management commands against production PostgreSQL from your machine, add Railway's `DATABASE_PUBLIC_URL` to `.env` as `DATABASE_URL`.

## Tests

```bash
source venv/bin/activate
pytest
```

Tests use `leaderlodge.settings.test` (see `pytest.ini`). You do not need a `.env` file to run pytest, but you need one for `manage.py` commands.

## Importing historical games

See [Importing game history](importing.md) for seed file layout, player mapping, and the `import_games` management command.

Quick example:

```bash
python manage.py import_games \
  --group "manpearl" \
  --game-type dominos \
  data/seeds/dominos/dominos_seed_2026-06-16.xlsx
```
