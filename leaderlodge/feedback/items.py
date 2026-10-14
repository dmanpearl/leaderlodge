"""Feedback form item codes (game types plus app-area tags)."""

from django.db import models

from leaderlodge.games.registry import GAME_TYPES, game_type_choices


class FeedbackAppItem(models.TextChoices):
    OTHER = "other", "Other"
    LOCATION = "location", "Location"
    USER_ACCOUNTS = "user_accounts", "User Accounts"
    GROUPS = "groups", "Groups"
    LEADERBOARDS = "leaderboards", "Leaderboards"
    AI_GAME_ENTRY = "ai_game_entry", "AI game entry"


def feedback_item_choices() -> list[tuple[str, str]]:
    games = sorted(game_type_choices(), key=lambda pair: pair[1].casefold())
    return [*FeedbackAppItem.choices, *games]


def is_valid_feedback_item_code(code: str) -> bool:
    return code in FeedbackAppItem.values or code in GAME_TYPES


def feedback_item_label(code: str) -> str:
    if not code:
        return FeedbackAppItem.OTHER.label
    if code in FeedbackAppItem.values:
        return FeedbackAppItem(code).label
    game_type = GAME_TYPES.get(code)
    return game_type.name if game_type else code
