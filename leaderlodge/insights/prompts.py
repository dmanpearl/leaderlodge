"""Prompt templates for AI insights."""

from __future__ import annotations

import json
import re
from typing import Any

PROMPT_VERSION = 2

PLAYER_INSIGHT_SYSTEM_PROMPT = """You are an analyst for LeaderLodge, a friendly game-night stats app.

You will receive JSON with computed stats for one player in one group.

Rules:
- Use ONLY facts present in the JSON. Do not invent games, scores, or ranks.
- If data_quality.sparse is true, say data is limited and keep the answer short.
- Do not mention other products or APIs.
- Write in clear, encouraging prose suitable for friends at game night.
- Output markdown only: at most one short heading, then 2-4 short paragraphs OR up to 5 bullet points.
- Never claim to predict future performance.
"""

PRESET_STRENGTHS = "strengths"
PRESET_WEAKNESSES = "weaknesses"
PRESET_SUPERPOWER = "superpower"
PRESET_CUSTOM = "custom"

PRESET_IDS = (
    PRESET_STRENGTHS,
    PRESET_WEAKNESSES,
    PRESET_SUPERPOWER,
    PRESET_CUSTOM,
)

_PRESET_MESSAGES: dict[str, str] = {
    PRESET_STRENGTHS: "Summarize this player's strengths based on the JSON.",
    PRESET_WEAKNESSES: (
        "Where does this player struggle relative to the group? Be constructive."
    ),
    PRESET_SUPERPOWER: (
        "In one memorable paragraph, what is the best thing about this player's performance?"
    ),
}

MAX_CUSTOM_QUESTION_LENGTH = 500
_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def sanitize_custom_question(raw: str) -> str:
    cleaned = _CONTROL_CHAR_RE.sub("", raw).strip()
    return cleaned[:MAX_CUSTOM_QUESTION_LENGTH]


def resolve_preset(raw: str) -> str:
    preset = (raw or PRESET_STRENGTHS).strip()
    if preset in PRESET_IDS:
        return preset
    return PRESET_STRENGTHS


def render_user_message(
    *,
    context: dict[str, Any],
    preset: str,
    question: str = "",
) -> str:
    resolved = resolve_preset(preset)
    if resolved == PRESET_CUSTOM:
        custom = sanitize_custom_question(question)
        if not custom:
            raise ValueError("A custom question is required.")
        prompt_text = custom
    else:
        prompt_text = _PRESET_MESSAGES[resolved]

    payload = json.dumps(context, indent=2, sort_keys=True)
    return f"{payload}\n\nQuestion: {prompt_text}"
