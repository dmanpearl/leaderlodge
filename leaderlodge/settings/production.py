"""
Production settings. Selected on Railway via:

    DJANGO_SETTINGS_MODULE=leaderlodge.settings.production
"""

from .base import *  # noqa: F403

DEBUG = False

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
] + MIDDLEWARE[1:]  # noqa: F405

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
# Safari can break same-origin fetch after sleep/POST when COOP is
# same-origin (breaking-news pattern). Single-host app: COOP unused.
SECURE_CROSS_ORIGIN_OPENER_POLICY = None

