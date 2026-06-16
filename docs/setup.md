# Local development

See [README.md](../README.md) for first-time bootstrap (venv creation, install, run).

## Prerequisites

- Python 3.11+

## Daily workflow

```bash
cd ~/pixelmonks/leaderlodge
source venv/bin/activate
python manage.py runserver
```

On Windows: `venv\Scripts\activate`

## First run after migrations are approved

```bash
source venv/bin/activate
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Open http://127.0.0.1:8000/

## Settings

| Module | Use |
|--------|-----|
| `leaderlodge.settings.local` | Local dev (SQLite, default) |
| `leaderlodge.settings.production` | Railway / PostgreSQL |

Set `DJANGO_SETTINGS_MODULE=leaderlodge.settings.production` in production.

## Tests

```bash
source venv/bin/activate
pytest
```
