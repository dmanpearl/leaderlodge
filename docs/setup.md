# Local development

See [README.md](../README.md) for first-time bootstrap (venv, `.env`, install, run).

## Prerequisites

- Python 3.11+

## Environment variables

```bash
cp .env.example .env
```

Set `DJANGO_SECRET_KEY` in `.env` before running any Django command. See README.md for key generation.

### AI Insights (optional)

After `pip install -r requirements-dev.txt`, set in `.env`:

- `INSIGHTS_ENABLED=true`
- `OPENAI_API_KEY` and `GOOGLE_AI_API_KEY` (from OpenAI and Google AI Studio)
- Leave `INSIGHTS_RATE_LIMITS_ENABLED=false` for MVP

Open a rank detail page and use the **Insights** button. See [ai-insights.md](ai-insights.md).

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
python manage.py setup_site_settings --email=you@example.com
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

See [Importing game history](importing.md) for seed file layout, player mapping, and the `import_games` management command. Full command inventory: [Management commands](management-commands.md).

Quick example:

```bash
python manage.py import_games \
  --group "manpearl" \
  --game-type dominos \
  data/seeds/dominos/dominos_seed_2026-07-16.xlsx
```

## Demo group (public read-only)

Anonymous visitors can browse the **Demo** group when `DEMO_MODE_ENABLED` is true (default). See [Importing game history — Demo group seeds](importing.md#demo-group-seeds) for spreadsheet paths and formats.

After `migrate` and `createsuperuser`:

```bash
python manage.py setup_demo
```

This creates the **Demo** group, sets `is_demo=True`, and imports all five bundled demo seed files (dominos, backgammon, Progressive Rummy, Mah Jongg, and Pickleball). Re-running is idempotent.

Log out and open http://127.0.0.1:8000/ to confirm the demo landing page. Set `DEMO_MODE_ENABLED=false` in `.env` or Railway variables to disable public demo browsing.

### Railway production

After deploy (migrate runs automatically via `railway.json`):

```bash
railway link
railway run python manage.py createsuperuser   # first time only
railway run python manage.py setup_demo
```

Use `--owner USERNAME` if you have multiple superusers and want a specific group owner. No Django admin step is required to set **Is demo**.

## Site settings (admin notifications)

LeaderLodge can email an operator when users sign up, invites are sent or accepted, games are edited, or feedback is submitted. Settings live in a single **Site settings** row (Django admin, not environment variables).

### What `setup_site_settings` does

```bash
python manage.py setup_site_settings --email=you@example.com
```

`--email` is **required**. The command creates or updates the site settings singleton:

- Sets **notify email** to the address you pass
- Turns **on** all notification types: signup, invite sent, invite accepted, game change, feedback

Re-running is safe. It refreshes the email address and fills in an empty notifications map; it does not wipe toggles you already saved.

There is **no default email in code**. Until you set an email here or in admin, notifications are skipped even when toggles are on.

**Local:** run once after `migrate` and `createsuperuser`.

**Production:**

```bash
railway run python manage.py setup_site_settings --email=you@example.com
```

### Configure in Django admin instead

1. Sign in as staff at `/admin/`.
2. Open **Core** > **Site settings**.
3. If no row exists, click **Add site settings** (only one row is allowed).
4. Set **Notify email** and check the notification types you want.
5. Save.

To change settings later, open the existing row and edit the same fields. Deleting the row is disabled.

Notification types are stored as JSON internally; the admin form shows checkboxes only.

### Replacing an initial `core` migration locally

If you already applied an older `core.0001_*` migration and the migration file was renamed or rewritten (for example **Site configuration** to **Site settings**), `python manage.py migrate core zero` may report **No migrations to apply** because Django only sees the new file on disk while `django_migrations` still lists the old name.

Clean up the orphan record and old table, then re-run setup:

```bash
python manage.py shell -c "
from django.db import connection
with connection.cursor() as c:
    c.execute(\"DELETE FROM django_migrations WHERE app='core' AND name='0001_site_configuration'\")
    c.execute('DROP TABLE IF EXISTS core_siteconfiguration')
"

python manage.py setup_site_settings --email=you@example.com
```

You should have only `core_sitesettings` and one row in `django_migrations` for `core.0001_site_settings`. Use this on local SQLite only when the old migration was never deployed to production.

Before enabling AI Insights in production, add `INSIGHTS_ENABLED`, `OPENAI_API_KEY`, and `GOOGLE_AI_API_KEY` to Railway Variables. See [ai-insights.md](ai-insights.md#railway-promotion-do-before-enabling-insights-in-production).

## User accounts

Self-service signup, login (email or username), and password reset are at `/accounts/signup/`, `/accounts/login/`, and `/accounts/password-reset/`.

Locally, outbound email uses the **console backend** (messages print in the runserver terminal). Production uses **Brevo's HTTPS API** via django-anymail; see [Production email (Brevo)](#production-email-brevo) below.

### Preview transactional emails

Use `send_sample_email` to render welcome and password-reset templates without going through signup or the reset form. Also listed in [Management commands](management-commands.md#send_sample_email).

**Print to the terminal (no mail sent):**

```bash
python manage.py send_sample_email --type welcome --user YOUR_USERNAME --print-only
python manage.py send_sample_email --type password-reset --user YOUR_USERNAME --print-only
```

The account named by `--user` supplies context (username, verification/reset links). Output goes to stdout; nothing is queued.

**Send using your configured mail backend:**

```bash
python manage.py send_sample_email --type welcome --user YOUR_USERNAME
python manage.py send_sample_email --type password-reset --user YOUR_USERNAME
```

Locally this uses the **console backend** unless you set `BREVO_API_KEY` or SMTP vars in `.env`. To deliver to your inbox, either:

- Set `BREVO_API_KEY` and `DEFAULT_FROM_EMAIL` in `.env` for a local send through Brevo, or
- Run against production settings and DB: `railway run python manage.py send_sample_email ...`

Useful options:

| Flag | Purpose |
|------|---------|
| `--to you@example.com` | Send to a different address (default: the user's email on file) |
| `--site-url https://leaderlodge.com` | Hostname/protocol for links in the message body |

The user must exist and should have an email on file unless you pass `--to`.

## Production email (Brevo)

LeaderLodge uses a **separate Brevo account** (free tier) for outbound mail from `@leaderlodge.com`. Your **pixelmonks.com** contact form can stay on **Resend** unchanged. You do not need a second Resend domain or the paid Resend plan.

Porkbun is only used for **DNS records** on `leaderlodge.com` (not mailboxes). Railway holds the Brevo API key.

**Railway blocks outbound SMTP** (ports 587/465). Password reset must use Brevo's **API**, not `smtp-relay.brevo.com`. The app uses django-anymail when `BREVO_API_KEY` is set.

### Why Brevo for LeaderLodge

| | **Resend (pixelmonks.com)** | **Brevo (leaderlodge.com)** |
|--|--|--|
| Account | Keep as-is for pixelmonks.com | New free Brevo account for LeaderLodge only |
| Domain | `pixelmonks.com` | `leaderlodge.com` only |
| Cost | Your current plan | Free tier (300 emails/day; plenty for password reset and invites) |

### Website vs email hostnames

| Hostname | Role |
|----------|------|
| `leaderlodge.com` | Website and password-reset links when users visit the apex URL |
| `www.leaderlodge.com` | Website and password-reset links when users visit the www URL |
| `@leaderlodge.com` (e.g. `noreply@leaderlodge.com`) | **From** address in Brevo (apex domain only; never `www@...`) |

Both website hostnames are already in `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS`. Password-reset emails use whichever hostname the user submitted the form from, so links work on both.

**Before email setup**, confirm both URLs load the app:

1. Railway > your web service > **Networking** > add custom domains `leaderlodge.com` and `www.leaderlodge.com` if not already present.
2. In Porkbun DNS for `leaderlodge.com`:
   - **Apex** (`@`): ALIAS/ANAME to Railway's target (from `railway domain status` or the Railway networking panel).
   - **www**: CNAME to Railway's www target (or to `leaderlodge.com` if Porkbun supports flattening to the same target).
3. Open `https://leaderlodge.com/` and `https://www.leaderlodge.com/` and confirm both show LeaderLodge.

Brevo domain authentication uses the **apex** domain only (`leaderlodge.com`). That covers sending from `@leaderlodge.com` addresses. You do **not** add `www.leaderlodge.com` as a separate domain in Brevo.

### Overview

| Piece | Role |
|-------|------|
| **Brevo** | Sends LeaderLodge password-reset and future invite mail |
| **Porkbun DNS** | Web records for apex + www; plus TXT/CNAME records Brevo requires for mail |
| **Railway variables** | Brevo API key and from-address |

### Step 1: Create a Brevo account for LeaderLodge

1. Sign up at [brevo.com](https://www.brevo.com) with an email you check (can be the same person as pixelmonks.com; this is a **separate account** from Resend).
2. Complete Brevo's account verification if prompted.
3. You do **not** need a paid Brevo plan for LeaderLodge.

### Step 2: Authenticate `leaderlodge.com` in Brevo

1. In Brevo, open **Settings** (gear) > **Senders, Domains & Dedicated IPs** > **Domains**.
2. Click **Add a domain** and enter `leaderlodge.com` (apex only, not `www.leaderlodge.com`).
3. Brevo shows DNS records to add (typically DKIM CNAME/TXT and an SPF TXT). Leave that page open.

These mail records live in the same Porkbun zone as your web DNS. They do not replace your existing apex/www web records.

### Step 3: Add Brevo DNS records in Porkbun

1. Log in to [porkbun.com](https://porkbun.com).
2. **Domain Management** > **leaderlodge.com** > **DNS** (Edit DNS).
3. For **each record Brevo lists**, add a matching row in Porkbun:
   - **Type**: same as Brevo (CNAME or TXT)
   - **Host**: copy exactly from Brevo (not `@` or `www` unless Brevo says so)
   - **Answer / Value**: copy exactly from Brevo
4. Save. Do **not** remove or change existing apex/www web records unless Brevo or Railway explicitly tells you to.
5. Back in Brevo, click to **Authenticate** / verify the domain.
6. DNS can take 5 minutes to a few hours. Wait until Brevo shows the domain as authenticated.

You are editing **DNS**, not Porkbun email forwarding. No mailbox setup is required.

### Step 4: Create a Brevo API key and from-address

1. In Brevo, go to **Settings** > **SMTP & API** > **API Keys**.
2. Click **Generate a new API key** (name it e.g. `LeaderLodge Railway`). Copy the key (`xkeysib-...`); you may not see it again.
3. This is an **API v3 key**, not an SMTP key. Do not use the SMTP tab key here.
4. After domain authentication, use this from-address:

   `LeaderLodge <noreply@leaderlodge.com>`

   You do not need a real inbox at that address. Do not use `www.leaderlodge.com` in the from-address.

### Step 5: Railway environment variables

In the LeaderLodge Railway service, add:

| Variable | Value |
|----------|--------|
| `BREVO_API_KEY` | your Brevo API v3 key (`xkeysib-...`) |
| `DEFAULT_FROM_EMAIL` | `LeaderLodge <noreply@leaderlodge.com>` |

Redeploy after saving. When `BREVO_API_KEY` is set, the app uses Brevo's HTTPS API (django-anymail).

You can remove the old SMTP variables (`EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS`) from Railway; they are not used when `BREVO_API_KEY` is set.

### Step 6: Test on production

Test **both** website hostnames:

1. Use an account with an email you control (or sign up fresh on production).
2. Visit `https://leaderlodge.com/accounts/password-reset/`, submit the form, and complete the reset flow.
3. Repeat from `https://www.leaderlodge.com/accounts/password-reset/`.
4. Confirm each email's reset link uses the same hostname you submitted from (`leaderlodge.com` vs `www.leaderlodge.com`).
5. Check the Brevo **Transactional** / **Email** logs and your inbox (including spam).

Optional smoke test from your laptop (uses Railway production variables):

```bash
railway run python manage.py shell -c "
from django.conf import settings
from django.core.mail import send_mail
send_mail(
    'LeaderLodge test',
    'Brevo API works.',
    settings.DEFAULT_FROM_EMAIL,
    ['YOUR_EMAIL@example.com'],
)
"
```

**If you use a local `.env` file:** `load_dotenv(override=True)` in settings makes `.env` win over variables injected by `railway run`. For this smoke test, comment out any `BREVO_API_KEY` or `EMAIL_*` lines in `.env` so Railway's values are used.

Check which backend Django sees:

```bash
railway run python manage.py shell -c "
from django.conf import settings
print('EMAIL_BACKEND', '=', settings.EMAIL_BACKEND)
print('DEFAULT_FROM_EMAIL', '=', settings.DEFAULT_FROM_EMAIL)
print('BREVO_API_KEY set', '=', bool(getattr(settings, 'ANYMAIL', {}).get('BREVO_API_KEY')))
"
```

### Troubleshooting

- **500 / worker timeout on password reset (~30s)**: Railway is blocking SMTP. Set `BREVO_API_KEY` (API v3 key) and redeploy. Remove reliance on `EMAIL_HOST` SMTP vars.
- **535 Authentication failed (`SMTPAuthenticationError`)** on laptop only: wrong SMTP credentials, or you are still on the SMTP backend locally. Production should use `anymail.backends.brevo.EmailBackend` when `BREVO_API_KEY` is set.
- **Brevo shows sent, nothing in inbox**: check spam; confirm domain authentication is green in Brevo.
- **302 but no email received**: Django always redirects to "Check your email" even when no account matches (anti-enumeration). Check:
  - The address on the form **exactly matches** the user's `email` field in Admin (accounts created before signup, or via `createsuperuser`, often have a blank email).
  - Brevo **Transactional** log for a send attempt at that time.
  - Railway deploy logs for `Password reset requested for email with no active matching account` or `Password reset email delivery failed`.
  - Run against production DB: `railway run python manage.py shell -c "from django.contrib.auth import get_user_model; print(list(get_user_model().objects.filter(email__iexact='YOUR_EMAIL').values('username','email','is_active')))"`
- **Reset link host looks wrong**: links mirror the hostname on the reset form; both apex and www are valid if both resolve to the app.
- **Local dev**: no Railway vars needed; watch the runserver console for reset links.
