"""Apply lock/type/unlock URL control params and redirect when needed."""

from __future__ import annotations

from django.http import HttpRequest, HttpResponseRedirect, QueryDict

from leaderlodge.accounts.game_selection import (
    URL_LOCK_KEYS,
    URL_TYPE_KEYS,
    URL_UNLOCK_KEY,
    is_game_type_locked,
    lock_game_type,
    locked_game_type_code,
    persist_game_type_code,
    unlock_game_type,
)
from leaderlodge.games.registry import resolve_game_type_token

# Params that are applied then stripped from the URL (one-shot controls).
_STRIP_KEYS = (*URL_LOCK_KEYS, URL_UNLOCK_KEY)


def _first_present(params: QueryDict, keys: tuple[str, ...]) -> str | None:
    for key in keys:
        if key in params:
            return params.get(key, "")
    return None


def control_params_present(request: HttpRequest) -> bool:
    """True when lock/unlock or type short-controls need handling."""
    if any(key in request.GET for key in _STRIP_KEYS):
        return True
    # type/t also apply preference / unlock-if-different (not stripped).
    return any(key in request.GET for key in URL_TYPE_KEYS)


def apply_game_type_url_controls(request: HttpRequest) -> bool:
    """Apply unlock / lock / type from GET.

    Precedence: unlock, then lock/l, then type/t.
    Returns True when a redirect strip of lock/unlock params is needed.
    """
    needs_strip = any(key in request.GET for key in _STRIP_KEYS)

    if URL_UNLOCK_KEY in request.GET:
        if is_game_type_locked(request):
            code = locked_game_type_code(request)
            unlock_game_type(request)
            if code:
                persist_game_type_code(request, code)

    lock_raw = _first_present(request.GET, URL_LOCK_KEYS)
    if lock_raw is not None:
        code = resolve_game_type_token(lock_raw)
        if code:
            lock_game_type(request, code)

    type_raw = _first_present(request.GET, URL_TYPE_KEYS)
    if type_raw is not None:
        code = resolve_game_type_token(type_raw)
        if code:
            if is_game_type_locked(request):
                locked = locked_game_type_code(request)
                if code != locked:
                    unlock_game_type(request)
                    persist_game_type_code(request, code)
            else:
                persist_game_type_code(request, code)

    return needs_strip


def redirect_without_control_params(request: HttpRequest) -> HttpResponseRedirect:
    """Redirect to the same path with lock/unlock params removed (keep type)."""
    params = request.GET.copy()
    for key in _STRIP_KEYS:
        params.pop(key, None)
    query = params.urlencode()
    url = request.path
    if query:
        url = f"{url}?{query}"
    return HttpResponseRedirect(url)
