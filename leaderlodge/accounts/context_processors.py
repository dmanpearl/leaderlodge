from leaderlodge.accounts.email_verification import is_email_verified
from leaderlodge.accounts.game_selection import (
    is_game_type_locked,
    locked_game_type_code,
    preferred_game_type_code,
)
from leaderlodge.accounts.group_selection import preferred_group_id
from leaderlodge.games.registry import GAME_TYPES, get_game_type
from leaderlodge.groups.names import format_user_display_name


def _query_string(**params: str) -> str:
    return "&".join(f"{key}={value}" for key, value in params.items() if value)


def ui_preferences_context(request):
    group_id = preferred_group_id(request)
    game_type_code = preferred_game_type_code(request)
    games_list_query = _query_string(group=group_id, type=game_type_code)
    leaderboards_query = _query_string(
        group=group_id,
        type=game_type_code,
    )
    user_email_verified = request.user.is_authenticated and is_email_verified(
        request.user
    )
    user_display_name = ""
    if request.user.is_authenticated:
        user_display_name = format_user_display_name(request.user)
    locked = is_game_type_locked(request)
    preferred_game_type_name = (
        get_game_type(game_type_code).name if game_type_code in GAME_TYPES else ""
    )
    return {
        "preferred_group_id": group_id,
        "preferred_game_type_code": game_type_code,
        "preferred_game_type_name": preferred_game_type_name,
        "preferred_games_list_query": games_list_query,
        "preferred_leaderboards_query": leaderboards_query,
        "game_type_locked": locked,
        "locked_game_type_code": locked_game_type_code(request) if locked else "",
        "user_email_verified": user_email_verified,
        "user_display_name": user_display_name,
    }
