from leaderlodge.accounts.game_selection import preferred_game_type_code


def game_selection_context(request):
    code = preferred_game_type_code(request)
    return {"preferred_game_type_code": code}
