"""Game-type-specific copy for Record Game AI entry help and placeholder."""

from __future__ import annotations

from leaderlodge.games.registry import GAME_TYPES, get_game_type

_LOCATION = "in Santa Monica"

# Casual example phrases; always end with the shared location cue.
_EXAMPLES: dict[str, str] = {
    "pickleball": (
        f"Lucas and Hudson 11 vs Amelia and Aurora 6, rally scoring, {_LOCATION}"
    ),
    "mahjongg": f"Lucas 120, Hudson 80, Amelia 45, American style, {_LOCATION}",
    "progressiverummy": f"Lucas 15, Hudson 42, Amelia 38, half game, {_LOCATION}",
    "dominos": f"Lucas 30 vs Hudson 12, {_LOCATION}",
    "backgammon": f"Lucas 5 vs Hudson 2, {_LOCATION}",
    "ginrummy": f"Lucas 112 vs Hudson 87, {_LOCATION}",
    "cribbage": f"Lucas 121 vs Hudson 98, {_LOCATION}",
    "phase10": f"Lucas 40, Hudson 85, Amelia 62, {_LOCATION}",
    "darts": f"Lucas beat Hudson in 501, {_LOCATION}",
    "cornhole": f"Lucas 21 vs Hudson 15, {_LOCATION}",
}


def ai_entry_example(game_type_code: str) -> str:
    """Example description for the AI entry placeholder and help popover."""
    if game_type_code in _EXAMPLES:
        return _EXAMPLES[game_type_code]
    if game_type_code in GAME_TYPES:
        return f"Lucas 21 vs Hudson 15, {_LOCATION}"
    return f"Lucas and Hudson 11 vs Amelia and Aurora 6, {_LOCATION}"


def ai_entry_help_content(game_type_code: str) -> str:
    """Popover body for the AI game entry info icon."""
    topics = ["players", "teams", "score", "location"]
    if game_type_code in GAME_TYPES:
        game_type = get_game_type(game_type_code)
        if game_type.score_types:
            topics.append(game_type.score_type_field_label.lower())
        if game_type.supports_half_game:
            topics.append("half game")
    topics_text = ", ".join(topics)
    example = ai_entry_example(game_type_code)
    return (
        f"Speak or type {topics_text}. AI will fill the game fields below "
        f"based on your casual description. Example: {example}."
    )
