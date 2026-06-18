# LeaderLodge

Mobile-friendly web app for tracking scores, rankings, and leaderboards for social games.

## Quick start (local)

From a fresh clone:

```bash
cd leaderlodge
python3 -m venv venv
source venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
```

Generate a secret key and paste it into `.env` as `DJANGO_SECRET_KEY`:

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Then:

```bash
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Open http://127.0.0.1:8000/

On Windows, activate the virtual environment with:

```text
venv\Scripts\activate
```

## Environment variables

The project requires `DJANGO_SECRET_KEY`. **Never commit secrets to Git.**

| Variable | Required | Purpose |
|----------|----------|---------|
| `DJANGO_SECRET_KEY` | Yes | Django crypto signing; set in `.env` locally, Railway Variables in production |
| `DJANGO_SETTINGS_MODULE` | Production | `leaderlodge.settings.production` on Railway; local dev defaults to `leaderlodge.settings.local` via `manage.py` |
| `DATABASE_URL` | Optional | PostgreSQL URL; unset locally (SQLite). Set in `.env` for `railway run` against production |
| `DJANGO_ALLOWED_HOST` | Optional | Extra hostname appended to `ALLOWED_HOSTS` / `CSRF_TRUSTED_ORIGINS` |

Copy `.env.example` to `.env` for local development. On Railway, set variables in the dashboard — do not upload a `.env` file.

`leaderlodge.com`, `www.leaderlodge.com`, and Railway's `RAILWAY_PUBLIC_DOMAIN` are already configured in settings. You do not need to set `ALLOWED_HOSTS` manually unless you add another hostname.

## Settings modules

| Module | Used by | DEBUG |
|--------|---------|-------|
| `leaderlodge.settings.local` | `manage.py runserver` (default) | `True` |
| `leaderlodge.settings.test` | `pytest` (automatic) | `True` |
| `leaderlodge.settings.production` | Railway via `gunicorn leaderlodge.wsgi` | `False` |

`manage.py` defaults to local settings via `setdefault`, so Railway's explicit `DJANGO_SETTINGS_MODULE=leaderlodge.settings.production` is preserved.

**Never run `collectstatic` locally.** Railway runs it on deploy. If `staticfiles/` exists locally, delete it: `rm -rf staticfiles/`

## Requirements

| File | Purpose |
|------|---------|
| `requirements.txt` | Production runtime (Railway installs this) |
| `requirements-dev.txt` | Local development (includes pytest, black) |

## Railway deployment

1. Push to the **`dev`** branch (Railway deploys from `dev`).
2. Add a **PostgreSQL** plugin and reference `DATABASE_URL` on the web service: `${{Postgres.DATABASE_URL}}`.
3. Set **`DJANGO_SECRET_KEY`** on the web service (generate a new key for production).
4. Deploy. `railway.json` runs migrate, collectstatic, and gunicorn on each deploy.
5. Custom domains and DNS are configured in Railway → Networking (see Porkbun ALIAS/CNAME targets from `railway domain status`).

### Bootstrap production data

```bash
railway link
railway run python manage.py createsuperuser
```

Create the `manpearl` group and link players in the app, then import seeds:

```bash
railway run python manage.py import_games -g manpearl --game-type dominos data/seeds/dominos/dominos_seed_2026-06-16.xlsx
railway run python manage.py import_games -g manpearl --game-type backgammon data/seeds/backgammon/backgammon_seed_2026-06-16.xlsx
railway run python manage.py import_games -g manpearl --game-type progressiverummy data/seeds/progressiverummy/progressiverummy_seed_2026-06-16.xlsx
```

For `railway run` from your laptop, add `DATABASE_URL` to `.env` using Railway's **public** Postgres URL (`railway variables get DATABASE_PUBLIC_URL`).

## Documentation

- [Local development setup](docs/setup.md) — settings, tests, day-to-day commands
- [Architecture](docs/architecture.md) — app layout, models, leaderboard design
- [Importing game history](docs/importing.md) — seed spreadsheets and `import_games`
