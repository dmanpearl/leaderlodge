"""
Local development settings. Selected by manage.py when DJANGO_SETTINGS_MODULE is unset.
"""

import os
import socket

from .base import *  # noqa: F403

DEBUG = True

# Hide runserver production warning in local dev only.
os.environ.setdefault("DJANGO_RUNSERVER_HIDE_WARNING", "true")


def _lan_address():
    """Return this machine's LAN address, or "" when offline.

    Opening a UDP socket sends no packets; it only asks the routing table
    which local address would be used to reach the internet.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except OSError:
        return ""
    finally:
        sock.close()


# Phone testing: `python manage.py runserver 0.0.0.0:8000` then browse to
# http://<lan-address>:8000/ from a device on the same network. ALLOWED_HOSTS
# is non-empty in base.py, so Django does not auto-allow it under DEBUG.
_lan_host = _lan_address()
if _lan_host and _lan_host not in ALLOWED_HOSTS:  # noqa: F405
    ALLOWED_HOSTS.append(_lan_host)  # noqa: F405


def no_store_middleware(get_response):
    """Stop phone browsers serving a stale copy of a dev page.

    The dev server sends no Cache-Control, so iOS Safari caches by heuristic
    and can hand back a page that still references a superseded ?v= asset,
    which looks exactly like a code change that did not take effect.
    """

    def middleware(request):
        response = get_response(request)
        response["Cache-Control"] = "no-store, must-revalidate"
        return response

    return middleware


MIDDLEWARE = MIDDLEWARE + [  # noqa: F405
    "leaderlodge.settings.local.no_store_middleware"
]
