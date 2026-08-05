"""Central game-type selection and lock, backed by per-user and session prefs."""

from __future__ import annotations

from django.http import HttpRequest

from leaderlodge.accounts.ui_settings import get_ui_settings, set_ui_settings
from leaderlodge.games.registry import GAME_TYPES, game_type_choices

GAME_SELECTION_NAMESPACE = "game_selection"
GAME_TYPE_CODE_KEY = "game_type_code"
LOCKED_KEY = "locked"
SESSION_GAME_TYPE_CODE = "game_selection.game_type_code"
SESSION_GAME_TYPE_LOCKED = "game_selection.locked"

# Inbound URL control params (stripped after apply by middleware).
URL_LOCK_KEYS = ("lock", "l")
URL_TYPE_KEYS = ("type", "t")
URL_UNLOCK_KEY = "unlock"
URL_CONTROL_KEYS = (*URL_LOCK_KEYS, *URL_TYPE_KEYS, URL_UNLOCK_KEY)


def all_game_type_codes() -> list[str]:
    return [code for code, _ in game_type_choices()]


def requested_game_type_token(request: HttpRequest) -> str:
    """Read type selection from GET ``type`` or short ``t``."""
    return request.GET.get("type", "").strip() or request.GET.get("t", "").strip()


def _saved_code(request: HttpRequest) -> str:
    if request.user.is_authenticated:
        return get_ui_settings(request.user, GAME_SELECTION_NAMESPACE).get(
            GAME_TYPE_CODE_KEY,
            "",
        )
    return request.session.get(SESSION_GAME_TYPE_CODE, "")


def _saved_locked(request: HttpRequest) -> bool:
    if request.user.is_authenticated:
        return bool(
            get_ui_settings(request.user, GAME_SELECTION_NAMESPACE).get(
                LOCKED_KEY, False
            )
        )
    return bool(request.session.get(SESSION_GAME_TYPE_LOCKED, False))


def _persist_code(request: HttpRequest, code: str) -> None:
    if code not in GAME_TYPES:
        return
    if request.user.is_authenticated:
        set_ui_settings(
            request.user,
            GAME_SELECTION_NAMESPACE,
            {GAME_TYPE_CODE_KEY: code},
        )
    else:
        request.session[SESSION_GAME_TYPE_CODE] = code


def _persist_locked(request: HttpRequest, locked: bool) -> None:
    if request.user.is_authenticated:
        set_ui_settings(
            request.user,
            GAME_SELECTION_NAMESPACE,
            {LOCKED_KEY: locked},
        )
    else:
        request.session[SESSION_GAME_TYPE_LOCKED] = locked


def preferred_game_type_code(request: HttpRequest) -> str:
    return _saved_code(request)


def is_game_type_locked(request: HttpRequest) -> bool:
    if not _saved_locked(request):
        return False
    code = _saved_code(request)
    return bool(code) and code in GAME_TYPES


def locked_game_type_code(request: HttpRequest) -> str:
    if not is_game_type_locked(request):
        return ""
    return _saved_code(request)


def available_game_type_codes(
    request: HttpRequest,
    *,
    candidates: list[str] | None = None,
) -> list[str]:
    """Codes available for UI selection, honoring an active lock."""
    base = [
        code
        for code in (candidates if candidates is not None else all_game_type_codes())
        if code in GAME_TYPES
    ]
    if not base:
        base = all_game_type_codes()
    locked = locked_game_type_code(request)
    if locked:
        if locked in base:
            return [locked]
        # Locked type not in candidate subset (e.g. unplayed filter): still force it.
        return [locked]
    return base


def lock_game_type(request: HttpRequest, code: str | None = None) -> str | None:
    """Lock to ``code`` (or current preference / first type). Returns locked code."""
    target = (code or _saved_code(request) or "").strip()
    if target not in GAME_TYPES:
        codes = all_game_type_codes()
        if not codes:
            return None
        target = codes[0]
    _persist_code(request, target)
    _persist_locked(request, True)
    return target


def unlock_game_type(request: HttpRequest) -> str:
    """Clear lock; keep preferred type (the previously locked code if any)."""
    code = _saved_code(request)
    _persist_locked(request, False)
    return code


def resolve_game_type_code(
    request: HttpRequest,
    *,
    requested: str,
    available_codes: list[str] | None = None,
) -> str:
    """
    Pick game type from request, saved preference, or first available code.

    When locked, always returns the locked type (ignores conflicting request).
    Persists to the user profile when logged in, or to the session for visitors.
    """
    from leaderlodge.games.registry import resolve_game_type_token

    locked = locked_game_type_code(request)
    if locked:
        return locked

    token = (requested or "").strip()
    resolved_request = resolve_game_type_token(token) if token else None

    valid_available = available_game_type_codes(request, candidates=available_codes)

    saved = _saved_code(request)
    explicit = resolved_request is not None and resolved_request in valid_available
    if explicit:
        chosen = resolved_request
    elif saved in valid_available:
        chosen = saved
    else:
        chosen = valid_available[0]

    if explicit or not saved:
        _persist_code(request, chosen)

    return chosen


def persist_game_type_code(request: HttpRequest, code: str) -> None:
    _persist_code(request, code)


def clear_game_selection_session(request: HttpRequest) -> None:
    request.session.pop(SESSION_GAME_TYPE_CODE, None)
    request.session.pop(SESSION_GAME_TYPE_LOCKED, None)
