# LeaderLodge

Mobile-friendly web app for tracking scores, rankings, and leaderboards for social games.

## Quick start (local)

From a fresh clone in an empty directory:

```bash
cd leaderlodge
python3 -m venv venv
source venv/bin/activate
pip install -r requirements/local.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Open http://127.0.0.1:8000/

On Windows, activate the virtual environment with:

```text
venv\Scripts\activate
```

## Requirements

| File | Purpose |
|------|---------|
| `requirements/local.txt` | Local development (includes pytest) |
| `requirements/production.txt` | Railway / production deploy |
| `requirements/base.txt` | Shared runtime dependencies |

## Documentation

- [Local development setup](docs/setup.md) -- settings, tests, day-to-day commands
- [Architecture](docs/architecture.md) -- app layout, models, leaderboard design
- [Importing game history](docs/importing.md) -- seed spreadsheets and `import_games`

## Project status

Phase 1 MVP is in progress. Models are defined; migrations require explicit approval before running.
