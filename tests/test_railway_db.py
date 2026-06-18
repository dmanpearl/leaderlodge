import leaderlodge.railway_db as railway_db
import pytest


def test_running_on_railway_container(monkeypatch):
    monkeypatch.delenv("PORT", raising=False)
    monkeypatch.delenv("RAILWAY_ENVIRONMENT", raising=False)
    assert railway_db.running_on_railway_container() is False

    monkeypatch.setenv("PORT", "8080")
    monkeypatch.setenv("RAILWAY_ENVIRONMENT", "production")
    assert railway_db.running_on_railway_container() is True

    monkeypatch.delenv("PORT", raising=False)
    assert railway_db.running_on_railway_container() is False


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
    monkeypatch.setenv("PORT", "8080")
    monkeypatch.setenv("RAILWAY_ENVIRONMENT", "production")
    monkeypatch.delenv("DATABASE_PUBLIC_URL", raising=False)
    assert railway_db.resolve_database_url() == (
        "postgresql://u:p@postgres.railway.internal:5432/railway"
    )


def test_resolve_database_url_raises_when_public_unavailable(monkeypatch):
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://u:p@postgres.railway.internal:5432/railway",
    )
    monkeypatch.delenv("DATABASE_PUBLIC_URL", raising=False)
    monkeypatch.delenv("PORT", raising=False)
    monkeypatch.delenv("RAILWAY_ENVIRONMENT", raising=False)

    def fail_fetch():
        return ""

    monkeypatch.setattr(railway_db, "fetch_railway_postgres_public_url", fail_fetch)

    with pytest.raises(railway_db.RailwayDatabaseConfigError):
        railway_db.resolve_database_url()
