"""Prompt templates for AI insights."""

from __future__ import annotations

import json
import re
from typing import Any

PROMPT_VERSION = 3

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

GROUP_INSIGHT_SYSTEM_PROMPT = """You are an analyst for LeaderLodge, a friendly game-night stats app.

You will receive JSON with computed group-level stats: either a leaderboard snapshot or a Hall of Fame grid of period leaders.

Rules:
- Use ONLY facts present in the JSON. Do not invent games, scores, ranks, or players.
- If data_quality.sparse is true, say data is limited and keep the answer short.
- Do not mention other products or APIs.
- Write in clear, encouraging prose suitable for friends at game night.
- Output markdown only: at most one short heading, then 2-4 short paragraphs OR up to 5 bullet points.
- Never claim to predict future performance.
- Refer to players by display_label from the JSON.
"""

PRESET_STRENGTHS = "strengths"
PRESET_WEAKNESSES = "weaknesses"
PRESET_SUPERPOWER = "superpower"
PRESET_CUSTOM = "custom"

GROUP_PRESET_OVERVIEW = "overview"
GROUP_PRESET_STANDOUTS = "standouts"
GROUP_PRESET_COMPETITION = "competition"
GROUP_PRESET_DYNASTY = "dynasty"

PRESET_IDS = (
    PRESET_STRENGTHS,
    PRESET_WEAKNESSES,
    PRESET_SUPERPOWER,
    PRESET_CUSTOM,
)

GROUP_PRESET_IDS = (
    GROUP_PRESET_OVERVIEW,
    GROUP_PRESET_STANDOUTS,
    GROUP_PRESET_COMPETITION,
    GROUP_PRESET_DYNASTY,
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

_GROUP_PRESET_MESSAGES: dict[str, str] = {
    GROUP_PRESET_OVERVIEW: "Summarize this leaderboard or Hall of Fame snapshot for the group.",
    GROUP_PRESET_STANDOUTS: "Who stands out in this data and why? Name specific players.",
    GROUP_PRESET_COMPETITION: (
        "Describe the competition at the top. Who is close to the leader and what separates them?"
    ),
    GROUP_PRESET_DYNASTY: (
        "Which players dominate across periods or game types? Highlight repeat leaders and shifts over time."
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


def resolve_group_preset(raw: str, *, scope: str) -> str:
    preset = (raw or GROUP_PRESET_OVERVIEW).strip()
    if preset == GROUP_PRESET_DYNASTY and scope != "hall_of_fame":
        return GROUP_PRESET_COMPETITION
    if preset in GROUP_PRESET_IDS:
        return preset
    return GROUP_PRESET_OVERVIEW


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


def render_group_user_message(
    *,
    context: dict[str, Any],
    preset: str,
    question: str = "",
) -> str:
    scope = str(context.get("scope", ""))
    resolved = resolve_group_preset(preset, scope=scope)
    if resolved == PRESET_CUSTOM:
        custom = sanitize_custom_question(question)
        if not custom:
            raise ValueError("A custom question is required.")
        prompt_text = custom
    else:
        prompt_text = _GROUP_PRESET_MESSAGES[resolved]

    payload = json.dumps(context, indent=2, sort_keys=True)
    return f"{payload}\n\nQuestion: {prompt_text}"
