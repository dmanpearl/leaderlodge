"""Resolve Railway PostgreSQL URLs for local and deployed runtimes."""

from __future__ import annotations

import os
import shutil
import subprocess


class RailwayDatabaseConfigError(RuntimeError):
    """Raised when production Postgres cannot be reached from this runtime."""


def running_on_railway_container() -> bool:
    """True when Django is serving inside a deployed Railway container."""
    return bool(os.environ.get("PORT")) and bool(os.environ.get("RAILWAY_ENVIRONMENT"))


def fetch_railway_postgres_public_url() -> str:
    """
    Read DATABASE_PUBLIC_URL from the linked Postgres service via Railway CLI.

    Used when `railway run` injects a private DATABASE_URL that is not reachable
    from a developer laptop and DATABASE_PUBLIC_URL was not copied to the web
    service yet.
    """
    if not shutil.which("railway"):
        return ""

    service = os.environ.get("RAILWAY_POSTGRES_SERVICE", "Postgres")
    commands = [
        ["railway", "variable", "list", "--service", service, "--kv"],
        ["railway", "variables", "--service", service, "--kv"],
    ]
    prefix = "DATABASE_PUBLIC_URL="
    for command in commands:
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            continue

        if result.returncode != 0:
            continue

        for line in result.stdout.splitlines():
            if line.startswith(prefix):
                return line[len(prefix) :].strip()
    return ""


def resolve_database_url() -> str:
    """
    Choose the database URL for the current runtime.

    - Local dev with no DATABASE_URL: caller falls back to SQLite.
    - Railway container: private DATABASE_URL (postgres.railway.internal).
    - `railway run` from a laptop: public proxy URL when the private host is
      injected. Matches rating-ranch's DATABASE_PUBLIC_URL fallback.
    """
    db_url = os.environ.get("DATABASE_URL", "")
    if "railway.internal" not in db_url:
        return db_url

    public_url = os.environ.get("DATABASE_PUBLIC_URL", "")
    if public_url:
        return public_url

    if running_on_railway_container():
        return db_url

    public_url = fetch_railway_postgres_public_url()
    if public_url:
        return public_url

    raise RailwayDatabaseConfigError(
        "DATABASE_URL points at postgres.railway.internal, which is only "
        "reachable inside Railway. From your laptop, either:\n"
        "  1. Run `railway link` in this project and ensure the Railway CLI "
        "can read Postgres variables, or\n"
        "  2. Add DATABASE_PUBLIC_URL=${{Postgres.DATABASE_PUBLIC_URL}} to the "
        "web service in Railway, or\n"
        "  3. Put the public Postgres URL in .env as DATABASE_URL "
        "(see .env.example)."
    )
