"""Central game-type selection backed by per-user and session preferences."""

from __future__ import annotations

from django.http import HttpRequest

from leaderlodge.accounts.ui_settings import get_ui_settings, set_ui_settings
from leaderlodge.games.registry import GAME_TYPES, game_type_choices

GAME_SELECTION_NAMESPACE = "game_selection"
GAME_TYPE_CODE_KEY = "game_type_code"
SESSION_GAME_TYPE_CODE = "game_selection.game_type_code"


def all_game_type_codes() -> list[str]:
    return [code for code, _ in game_type_choices()]


def _saved_code(request: HttpRequest) -> str:
    if request.user.is_authenticated:
        return get_ui_settings(request.user, GAME_SELECTION_NAMESPACE).get(
            GAME_TYPE_CODE_KEY,
            "",
        )
    return request.session.get(SESSION_GAME_TYPE_CODE, "")


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


def preferred_game_type_code(request: HttpRequest) -> str:
    return _saved_code(request)


def resolve_game_type_code(
    request: HttpRequest,
    *,
    requested: str,
    available_codes: list[str] | None = None,
) -> str:
    """
    Pick game type from request, saved preference, or first available code.

    Persists to the user profile when logged in, or to the session for visitors.
    """
    valid_available = [
        code
        for code in (available_codes or all_game_type_codes())
        if code in GAME_TYPES
    ]
    if not valid_available:
        valid_available = all_game_type_codes()

    saved = _saved_code(request)
    explicit = requested in valid_available
    if explicit:
        chosen = requested
    elif saved in valid_available:
        chosen = saved
    else:
        chosen = valid_available[0]

    if explicit or not saved:
        _persist_code(request, chosen)

    return chosen


def persist_game_type_code(request: HttpRequest, code: str) -> None:
    _persist_code(request, code)
