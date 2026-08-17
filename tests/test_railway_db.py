import leaderlodge.railway_db as railway_db
import pytest


def test_running_on_railway_container(monkeypatch):
    monkeypatch.delenv("RAILWAY_ENVIRONMENT", raising=False)
    assert railway_db.running_on_railway_container() is False

    monkeypatch.setenv("RAILWAY_ENVIRONMENT", "production")
    assert railway_db.running_on_railway_container() is True


def test_resolve_database_url_uses_sqlite_when_unset(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("DATABASE_PUBLIC_URL", raising=False)
    assert railway_db.resolve_database_url() == ""


def test_resolve_database_url_keeps_public_url(monkeypatch):
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://u:p@proxy.rlwy.net:1234/railway",
    )
    monkeypatch.delenv("DATABASE_PUBLIC_URL", raising=False)
    assert "proxy.rlwy.net" in railway_db.resolve_database_url()


def test_resolve_database_url_swaps_internal_for_public_env(monkeypatch):
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://u:p@postgres.railway.internal:5432/railway",
    )
    monkeypatch.setenv(
        "DATABASE_PUBLIC_URL",
        "postgresql://u:p@proxy.rlwy.net:1234/railway",
    )
    assert railway_db.resolve_database_url() == (
        "postgresql://u:p@proxy.rlwy.net:1234/railway"
    )


def test_resolve_database_url_keeps_internal_on_container(monkeypatch):
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://u:p@postgres.railway.internal:5432/railway",
    )
    monkeypatch.setenv("RAILWAY_ENVIRONMENT", "production")
    monkeypatch.delenv("DATABASE_PUBLIC_URL", raising=False)
    monkeypatch.delenv("PORT", raising=False)
    assert railway_db.resolve_database_url() == (
        "postgresql://u:p@postgres.railway.internal:5432/railway"
    )


def test_resolve_database_url_raises_when_public_unavailable(monkeypatch):
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://u:p@postgres.railway.internal:5432/railway",
    )
    monkeypatch.delenv("DATABASE_PUBLIC_URL", raising=False)
    monkeypatch.delenv("RAILWAY_ENVIRONMENT", raising=False)

    def fail_fetch():
        return ""

    monkeypatch.setattr(railway_db, "fetch_railway_postgres_public_url", fail_fetch)

    with pytest.raises(railway_db.RailwayDatabaseConfigError):
        railway_db.resolve_database_url()


def test_fetch_railway_postgres_public_url_uses_variables_get(monkeypatch):
    monkeypatch.setenv("RAILWAY_POSTGRES_SERVICE", "Postgres")

    def fake_which(name):
        return "/usr/local/bin/railway" if name == "railway" else None

    def fake_run(command, **kwargs):
        if command[:3] == ["railway", "variables", "get"]:
            return type(
                "Result",
                (),
                {"returncode": 0, "stdout": "postgresql://u:p@proxy.rlwy.net:1/db"},
            )()
        return type("Result", (), {"returncode": 1, "stdout": ""})()

    monkeypatch.setattr(railway_db.shutil, "which", fake_which)
    monkeypatch.setattr(railway_db.subprocess, "run", fake_run)

    assert railway_db.fetch_railway_postgres_public_url() == (
        "postgresql://u:p@proxy.rlwy.net:1/db"
    )


def test_fetch_railway_postgres_public_url_falls_back_to_kv_list(monkeypatch):
    monkeypatch.setenv("RAILWAY_POSTGRES_SERVICE", "Postgres")

    def fake_which(name):
        return "/usr/local/bin/railway" if name == "railway" else None

    def fake_run(command, **kwargs):
        if command[:3] == ["railway", "variables", "get"]:
            return type("Result", (), {"returncode": 1, "stdout": ""})()
        if command[:3] == ["railway", "variable", "list"]:
            stdout = "DATABASE_URL=internal\nDATABASE_PUBLIC_URL=postgresql://public\n"
            return type("Result", (), {"returncode": 0, "stdout": stdout})()
        return type("Result", (), {"returncode": 1, "stdout": ""})()

    monkeypatch.setattr(railway_db.shutil, "which", fake_which)
    monkeypatch.setattr(railway_db.subprocess, "run", fake_run)

    assert railway_db.fetch_railway_postgres_public_url() == "postgresql://public"
