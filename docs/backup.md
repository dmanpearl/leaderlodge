# Production backup

Manual PostgreSQL dumps before milestone deploys. At current scale the
compressed custom-format dump is under **1 MB** and finishes in seconds; Railway
volume size on disk is much larger and is not the dump size. Railway volume
backups require a **Pro** plan and are not enabled on the free tier.

See also: [Railway deployment](../README.md#railway-deployment),
[Management commands](management-commands.md) (Django commands against production).

## When to dump

Run a backup **before** deploys that include:

- New or changed Django migrations
- Data migrations or one-off fixes against production
- Any change you would regret if the deploy failed mid-way

Routine code-only deploys with no schema changes are lower risk. Use judgment;
milestone deploys with migrations should always get a dump first.

## Prerequisites

On your laptop:

1. [Railway CLI](https://docs.railway.com/guides/cli) installed and linked:
   ```bash
   railway link
   ```
2. PostgreSQL client tools (`pg_dump`, `pg_restore`) whose **major version is
   greater than or equal to** Railway Postgres (currently **18**). Check:
   ```bash
   pg_dump --version
   ```
   If you see `18.x` or newer, you are done.

   **Client too old** (e.g. `14.x` from `postgresql@14`): install clients-only
   `libpq` and put it **ahead** of `/usr/local/bin` for dump commands. Do not
   `brew link libpq` if `postgresql@14` is still linked (symlink conflict).
   ```bash
   brew install libpq
   export PATH="$(brew --prefix libpq)/bin:$PATH"
   pg_dump --version   # expect 18.x
   ```
   Optional: add the `export PATH=...` line to `~/.zshrc` so new terminals pick
   it up. Your `postgresql@14` install stays for anything else that needs it.

   **Nothing installed yet:**
   ```bash
   brew install libpq
   export PATH="$(brew --prefix libpq)/bin:$PATH"
   ```

The Postgres service in Railway is named **`Postgres`** (default for
`RAILWAY_POSTGRES_SERVICE`).

## Dump production

Creates a timestamped custom-format dump under `backups/` (gitignored). The
custom format (`-Fc`) compresses well and restores with `pg_restore`. Ensure
`pg_dump --version` is **18 or newer** (see [Prerequisites](#prerequisites)).

```bash
mkdir -p backups
STAMP=$(date +%Y%m%d-%H%M%S)
OUT="backups/leaderlodge-${STAMP}.dump"
LOG="backups/leaderlodge-${STAMP}.log"
DATABASE_URL=$(railway variable list --service Postgres --kv \
  | sed -n 's/^DATABASE_PUBLIC_URL=//p')
test -n "$DATABASE_URL" || { echo "DATABASE_URL empty; run railway link"; exit 1; }

time pg_dump "$DATABASE_URL" \
  --format=custom \
  --no-owner \
  --no-acl \
  --verbose \
  --file="$OUT" \
  2>&1 | tee "$LOG"

ls -lh "$OUT"
pg_restore --list "$OUT" | head
```

The last line lists objects inside the dump (quick sanity check). Expect a
non-zero `.dump` file and no `pg_dump: error` lines in the log.

**Store the dump outside the repo** as well (e.g. a cloud folder or external
drive). Do not commit dump files.

### Progress and timing

`pg_dump` does not report a percentage. Use these signals instead:

| Method | What it tells you |
|--------|-------------------|
| `--verbose` + log file | Each table/object as it is dumped; confirms the job is alive |
| `time` (wraps the command above) | Total elapsed when finished |
| Second terminal: `watch -n 2 'ls -lh backups/*.dump 2>/dev/null \| tail -1'` | Output file growing (optional; often too fast to matter at current size) |

At current size, expect **seconds**, not minutes. Duration grows with data;
large databases can take many minutes.

### Plain SQL format (optional)

Human-readable `.sql` if you prefer `grep` or manual inspection. Larger on disk.

```bash
OUT="backups/leaderlodge-${STAMP}.sql"
time pg_dump "$DATABASE_URL" \
  --format=plain \
  --no-owner \
  --no-acl \
  --verbose \
  --file="$OUT" \
  2>&1 | tee "$LOG"
```

## Restore (local or staging only)

**Never restore over production** unless you are deliberately rolling back after
an incident and understand the downtime impact.

Custom-format dump to a **fresh empty** database:

```bash
# Example: local PostgreSQL database named leaderlodge_restore
createdb leaderlodge_restore
pg_restore --no-owner --no-acl --dbname=leaderlodge_restore backups/leaderlodge-YYYYMMDD-HHMMSS.dump
```

Plain SQL:

```bash
psql leaderlodge_restore < backups/leaderlodge-YYYYMMDD-HHMMSS.sql
```

Point Django at the restore DB with `DATABASE_URL` in `.env` and
`DJANGO_SETTINGS_MODULE=leaderlodge.settings.production` only on a machine you
control, not on Railway production.

## Pre-deploy safety checklist

Use before pushing migration-bearing changes to **`dev`** (Railway deploys from
`dev`). See [README: Railway deployment](../README.md#railway-deployment).

- [ ] **Snapshot:** Run the [dump command](#dump-production) above; confirm
  `ls -lh` shows a non-zero file; copy it off-repo.
- [ ] **Review migrations:** Read each new migration file. Flag destructive
  operations (`RemoveField`, `DeleteModel`, `RunSQL` that drops data, irreversible
  `AlterField`). Prefer reversible migrations or a data backfill plan.
- [ ] **Production shell discipline:** Do not run mutating `manage.py shell`,
  raw SQL, or ORM writes against production. Read-only inspection is fine
  (`railway run python manage.py shell` with SELECT-only queries, or
  `railway connect Postgres` for `\dt`, `\d+`, counts).
- [ ] **Deploy:** Push to `dev`; Railway runs `migrate` automatically via
  `railway.json`.
- [ ] **Smoke test:** After deploy, spot-check the site and admin for the area
  you changed.

## Railway automatic backups (optional)

Volume backups and point-in-time recovery (PITR) live on the Postgres service
**Backups** tab in Railway. They require a **Pro** workspace plan. If enabled,
they are a useful in-platform safety net but do **not** replace off-repo
`pg_dump` copies you control.

Without Pro, manual dumps before risky deploys are the backup plan.
