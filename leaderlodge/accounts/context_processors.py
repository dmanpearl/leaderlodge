from leaderlodge.accounts.game_selection import preferred_game_type_code
from leaderlodge.accounts.group_selection import preferred_group_id
from leaderlodge.accounts.email_verification import is_email_verified


def _query_string(**params: str) -> str:
    return "&".join(f"{key}={value}" for key, value in params.items() if value)


def ui_preferences_context(request):
    group_id = preferred_group_id(request)
    game_type_code = preferred_game_type_code(request)
    games_list_query = _query_string(group=group_id, game_type=game_type_code)
    leaderboards_query = _query_string(
        group=group_id,
        game_type_code=game_type_code,
    )
    user_email_verified = (
        request.user.is_authenticated and is_email_verified(request.user)
    )
    return {
        "preferred_group_id": group_id,
        "preferred_game_type_code": game_type_code,
        "preferred_games_list_query": games_list_query,
        "preferred_leaderboards_query": leaderboards_query,
        "user_email_verified": user_email_verified,
    }
