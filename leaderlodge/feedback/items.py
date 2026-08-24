"""Feedback form item codes (game types plus app-area tags)."""

from leaderlodge.games.registry import GAME_TYPES, game_type_choices

FEEDBACK_ITEM_OTHER = "other"
FEEDBACK_ITEM_LOCATION = "location"
FEEDBACK_ITEM_USER_ACCOUNTS = "user_accounts"
FEEDBACK_ITEM_GROUPS = "groups"
FEEDBACK_ITEM_LEADERBOARDS = "leaderboards"

FEEDBACK_ITEM_LABELS: dict[str, str] = {
    FEEDBACK_ITEM_OTHER: "Other",
    FEEDBACK_ITEM_LOCATION: "Location",
    FEEDBACK_ITEM_USER_ACCOUNTS: "User Accounts",
    FEEDBACK_ITEM_GROUPS: "Groups",
    FEEDBACK_ITEM_LEADERBOARDS: "Leaderboards",
}


def feedback_item_choices() -> list[tuple[str, str]]:
    non_game = [
        (FEEDBACK_ITEM_OTHER, FEEDBACK_ITEM_LABELS[FEEDBACK_ITEM_OTHER]),
        (FEEDBACK_ITEM_LOCATION, FEEDBACK_ITEM_LABELS[FEEDBACK_ITEM_LOCATION]),
        (
            FEEDBACK_ITEM_USER_ACCOUNTS,
            FEEDBACK_ITEM_LABELS[FEEDBACK_ITEM_USER_ACCOUNTS],
        ),
        (FEEDBACK_ITEM_GROUPS, FEEDBACK_ITEM_LABELS[FEEDBACK_ITEM_GROUPS]),
        (
            FEEDBACK_ITEM_LEADERBOARDS,
            FEEDBACK_ITEM_LABELS[FEEDBACK_ITEM_LEADERBOARDS],
        ),
    ]
    games = sorted(game_type_choices(), key=lambda pair: pair[1].casefold())
    return [*non_game, *games]


def is_valid_feedback_item_code(code: str) -> bool:
    if code in FEEDBACK_ITEM_LABELS:
        return True
    return code in GAME_TYPES


def feedback_item_label(code: str) -> str:
    if not code:
        return FEEDBACK_ITEM_LABELS[FEEDBACK_ITEM_OTHER]
    if code in FEEDBACK_ITEM_LABELS:
        return FEEDBACK_ITEM_LABELS[code]
    game_type = GAME_TYPES.get(code)
    return game_type.name if game_type else code
