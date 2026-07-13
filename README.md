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
python manage.py setup_site_settings --email=you@example.com
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
| `DATABASE_URL` | Optional | PostgreSQL URL; unset locally (SQLite). Optional `.env` override for `railway run` |
| `RAILWAY_POSTGRES_SERVICE` | Optional | Postgres service name in Railway (default: `Postgres`) |
| `DJANGO_ALLOWED_HOST` | Optional | Extra hostname appended to `ALLOWED_HOSTS` / `CSRF_TRUSTED_ORIGINS` |
| `DJANGO_TIME_ZONE` | Optional | IANA timezone for calendar dates (default: `America/Los_Angeles`) |
| `DEMO_MODE_ENABLED` | Optional | Public read-only demo group browsing (default: `true`) |
| `GOOGLE_PLACES_API_KEY` | Optional | Browser-restricted Google Places API key; enables the location Lookup button in game recording. See [docs/google-places.md](docs/google-places.md) |
| `DEFAULT_FROM_EMAIL` | Production | Brevo from-address (e.g. `LeaderLodge <noreply@leaderlodge.com>`) |
| `BREVO_API_KEY` | Production | Brevo API v3 key (`xkeysib-...`); uses HTTPS API (Railway blocks SMTP) |

Copy `.env.example` to `.env` for local development. On Railway, set variables in the dashboard - do not upload a `.env` file.

Production email setup (Brevo + Porkbun DNS): [docs/setup.md#production-email-brevo](docs/setup.md#production-email-brevo). pixelmonks.com can stay on Resend separately.

`leaderlodge.com`, `www.leaderlodge.com`, and Railway's `RAILWAY_PUBLIC_DOMAIN` are already configured in settings. You do not need to set `ALLOWED_HOSTS` manually unless you add another hostname.

## Settings modules

| Module | Used by | DEBUG |
|--------|---------|-------|
| `leaderlodge.settings.local` | `manage.py runserver` (default) | `True` |
| `leaderlodge.settings.test` | `pytest` (automatic) | `True` — isolated `test_db.sqlite3`, see [setup](docs/setup.md#tests) |
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
2. Add a **PostgreSQL** plugin. On the web service, reference:
   - `DATABASE_URL=${{Postgres.DATABASE_URL}}`
   - `DATABASE_PUBLIC_URL=${{Postgres.DATABASE_PUBLIC_URL}}` (for `railway run` from your laptop)
3. Set **`DJANGO_SECRET_KEY`** on the web service (generate a new key for production).
4. Deploy. `railway.json` runs migrate, collectstatic, and gunicorn on each deploy.
5. Custom domains and DNS are configured in Railway → Networking (see Porkbun ALIAS/CNAME targets from `railway domain status`).

`railway run python manage.py ...` resolves the public Postgres URL automatically. If the web service has no `DATABASE_PUBLIC_URL` reference yet, settings read it from the Postgres service via the linked Railway CLI. You can also put the public URL in `.env` as `DATABASE_URL` (rating-ranch style).

### Bootstrap production data

```bash
railway link
railway run python manage.py createsuperuser
railway run python manage.py setup_site_settings --email=you@example.com
```

Create the `manpearl` group and link players in the app, then import seeds:

```bash
railway run python manage.py import_games -g manpearl --game-type dominos data/seeds/dominos/dominos_seed_2026-06-16.xlsx
railway run python manage.py import_games -g manpearl --game-type backgammon data/seeds/backgammon/backgammon_seed_2026-06-16.xlsx
railway run python manage.py import_games -g manpearl --game-type progressiverummy data/seeds/progressiverummy/progressiverummy_seed_2026-06-16.xlsx
railway run python manage.py import_games -g manpearl --game-type pickleball data/seeds/pickleball/pickleball_demo_2026-07-04.xlsx
```

### Demo group (anonymous visitors)

After `createsuperuser`, load the public demo group and all five demo spreadsheets in one step:

```bash
railway run python manage.py setup_demo
```

This creates **Demo**, sets `is_demo=True`, and imports:

- `data/seeds/dominos/dominos_demo_2026-06-22.xlsx`
- `data/seeds/backgammon/backgammon_demo_2026-06-22.xlsx`
- `data/seeds/progressiverummy/progressiverummy_demo_2026-06-22.xlsx`
- `data/seeds/mahjongg/mahjongg_demo_2026-06-22.xlsx`
- `data/seeds/pickleball/pickleball_demo_2026-07-04.xlsx`

See [Demo group setup](docs/setup.md#demo-group-public-read-only) and [Importing — Demo seeds](docs/importing.md#demo-group-seeds) for local use, `--dry-run`, and manual import alternatives.

Admin notification email (signup, invites, game edits, feedback): [Site settings](docs/setup.md#site-settings-admin-notifications).

## Documentation

- [Local development setup](docs/setup.md) — settings, tests, day-to-day commands, **previewing transactional email**
- [Architecture](docs/architecture.md) — app layout, models, leaderboard design
- [Importing game history](docs/importing.md) — seed spreadsheets, `import_games`, and `setup_demo`
- [Google Places API](docs/google-places.md) — location lookup setup, billing, key restrictions, Railway deployment

## Git setup

Commit message format is documented in [`tools/git/git_template`](tools/git/git_template). Comment lines in that file are stripped when you save a commit.

From the repository root, point this clone at the template (writes `[commit] template` in `.git/config`, similar to global `~/.gitconfig`):

```bash
git config --local commit.template tools/git/git_template
```

Optional commit reference alias (global or local):

```bash
git config alias.ref "log --format='%h (%s)' -1"

# Example:
git ref 0a2c604
0a2c604 (feat(accounts): add send_sample_email dev command)
```
