"""
Shared settings for all environments. Never use this module as DJANGO_SETTINGS_MODULE.
Import it from local.py or production.py.
"""

import os
import urllib.parse
from pathlib import Path

from dotenv import load_dotenv

from leaderlodge.railway_db import resolve_database_url

# Load .env for local dev. On Railway, env vars are set in the dashboard.
# override=True lets local .env win over vars injected by `railway run`.
load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env", override=True)

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "")
if not SECRET_KEY:
    raise RuntimeError(
        "DJANGO_SECRET_KEY is not set. "
        "Copy .env.example to .env and fill in a secret key. "
        "See README.md § Environment variables."
    )

ALLOWED_HOSTS = [
    "localhost",
    "127.0.0.1",
    "0.0.0.0",
    "leaderlodge.com",
    "www.leaderlodge.com",
]
_railway_domain = os.environ.get("RAILWAY_PUBLIC_DOMAIN", "")
if _railway_domain and _railway_domain not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(_railway_domain)
_custom_host = os.environ.get("DJANGO_ALLOWED_HOST", "")
if _custom_host and _custom_host not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(_custom_host)

# Railway health checks and internal routing use these hostnames, not the
# custom domain. rating-ranch keeps its *.up.railway.app hostname here too.
if os.environ.get("RAILWAY_ENVIRONMENT"):
    for host in (
        ".up.railway.app",
        ".railway.internal",
        "healthcheck.railway.app",
    ):
        if host not in ALLOWED_HOSTS:
            ALLOWED_HOSTS.append(host)
    _private_domain = os.environ.get("RAILWAY_PRIVATE_DOMAIN", "")
    if _private_domain and _private_domain not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(_private_domain)

CSRF_TRUSTED_ORIGINS = [
    "https://leaderlodge.com",
    "https://www.leaderlodge.com",
]
if _railway_domain:
    _railway_origin = f"https://{_railway_domain}"
    if _railway_origin not in CSRF_TRUSTED_ORIGINS:
        CSRF_TRUSTED_ORIGINS.append(_railway_origin)
if _custom_host:
    _custom_origin = f"https://{_custom_host}"
    if _custom_origin not in CSRF_TRUSTED_ORIGINS:
        CSRF_TRUSTED_ORIGINS.append(_custom_origin)

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "leaderlodge.core",
    "leaderlodge.accounts",
    "leaderlodge.groups",
    "leaderlodge.games",
    "leaderlodge.leaderboards",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "leaderlodge.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "leaderlodge.wsgi.application"

# Locally: SQLite. On Railway: DATABASE_URL from Postgres.
# Railway's private host (postgres.railway.internal) is only reachable inside
# the platform. For `railway run` from a laptop, resolve_database_url() swaps
# to DATABASE_PUBLIC_URL or reads it from the Postgres service via Railway CLI.
_db_url = resolve_database_url()
if _db_url:
    _parsed = urllib.parse.urlparse(_db_url)
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": _parsed.path.lstrip("/"),
            "USER": _parsed.username,
            "PASSWORD": _parsed.password,
            "HOST": _parsed.hostname,
            "PORT": str(_parsed.port or 5432),
            "CONN_MAX_AGE": 600,
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
            "OPTIONS": {
                "timeout": 30,
            },
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "core:dashboard"
LOGOUT_REDIRECT_URL = "accounts:login"

MIN_GAMES_FOR_LEADERBOARD = 1
