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
    "anymail",
    "leaderlodge.core",
    "leaderlodge.accounts",
    "leaderlodge.groups",
    "leaderlodge.games",
    "leaderlodge.leaderboards",
    "leaderlodge.insights",
    "leaderlodge.feedback",
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
                "leaderlodge.core.context_processors.demo_context",
                "leaderlodge.core.context_processors.table_formats",
                "leaderlodge.core.context_processors.navbar_context",
                "leaderlodge.core.context_processors.brand_context",
                "leaderlodge.core.context_processors.insights_debug_context",
                "leaderlodge.accounts.context_processors.ui_preferences_context",
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
# Calendar dates (e.g. game "played on") use this zone. UTC makes late-evening
# US games default to tomorrow's date.
TIME_ZONE = os.environ.get("DJANGO_TIME_ZONE", "America/Los_Angeles")
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "core:dashboard"
LOGOUT_REDIRECT_URL = "core:dashboard"

# Keep CSRF cookie across sleep/wake; slide session on activity (breaking-news pattern).
CSRF_COOKIE_AGE = 60 * 60 * 24 * 365
SESSION_COOKIE_AGE = 60 * 60 * 24 * 14
SESSION_SAVE_EVERY_REQUEST = True

DEMO_MODE_ENABLED = os.environ.get("DEMO_MODE_ENABLED", "true").lower() in (
    "true",
    "1",
    "yes",
)

MIN_GAMES_FOR_LEADERBOARD = 1
LEADERBOARD_VESTING_COUNT = 14
LEADERBOARD_VESTING_FACTOR = 0.5

# AI Insights — see docs/ai-insights.md
INSIGHTS_ENABLED = os.environ.get("INSIGHTS_ENABLED", "false").lower() in (
    "true",
    "1",
    "yes",
)
# Off for MVP; flip on when usage grows. Requires shared cache (Redis) on multi-worker prod.
INSIGHTS_RATE_LIMITS_ENABLED = os.environ.get(
    "INSIGHTS_RATE_LIMITS_ENABLED",
    "false",
).lower() in ("true", "1", "yes")
# Optional deploy-time limit overrides (merged onto limits_defaults.DEFAULT_INSIGHT_LIMITS).
# Example: {"authenticated": {"daily": 150}, "models": {"gpt-4o-mini": {"daily": 20}}}
INSIGHTS_LIMITS: dict = {}
INSIGHTS_LIMITS_JSON = os.environ.get("INSIGHTS_LIMITS_JSON", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
GOOGLE_AI_API_KEY = os.environ.get("GOOGLE_AI_API_KEY", "")

DEFAULT_FROM_EMAIL = os.environ.get(
    "DEFAULT_FROM_EMAIL",
    "LeaderLodge <noreply@leaderlodge.com>",
)
SERVER_EMAIL = DEFAULT_FROM_EMAIL

BREVO_API_KEY = os.environ.get("BREVO_API_KEY", "")

if BREVO_API_KEY:
    # Railway blocks outbound SMTP; Brevo's HTTPS API works from the platform.
    EMAIL_BACKEND = "anymail.backends.brevo.EmailBackend"
    ANYMAIL = {
        "BREVO_API_KEY": BREVO_API_KEY,
    }
else:
    EMAIL_BACKEND = os.environ.get(
        "EMAIL_BACKEND",
        "django.core.mail.backends.console.EmailBackend",
    )
    EMAIL_HOST = os.environ.get("EMAIL_HOST", "")
    if EMAIL_HOST:
        EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
        EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
        EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
        EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", "true").lower() in (
            "true",
            "1",
            "yes",
        )
        EMAIL_TIMEOUT = int(os.environ.get("EMAIL_TIMEOUT", "10"))
        if EMAIL_BACKEND == "django.core.mail.backends.console.EmailBackend":
            EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
