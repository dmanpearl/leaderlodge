"""Parse a spoken or typed game entry into a Record Game draft."""

from __future__ import annotations

import json
import re
from typing import Any

from django.contrib.auth.models import AbstractBaseUser

from leaderlodge.games.last_location import (
    last_recorded_location_name,
    last_recorded_score_type,
)
from leaderlodge.games.registry import (
    GAME_TYPES,
    game_type_has_score_type,
    get_game_type,
    normalize_score_type,
)
from leaderlodge.groups.models import Group
from leaderlodge.insights.router import complete_insight
from leaderlodge.insights.tools.locations import resolve_location_query
from leaderlodge.insights.tools.players import resolve_player_query

_JSON_FENCE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)
_GROUP_HINT = re.compile(
    r"\b(?:in|for|with)\s+group\b|\bgroup\s+[A-Za-z0-9][\w' -]{0,40}",
    re.IGNORECASE,
)
_DATE_HINT = re.compile(
    r"\b(?:on\s+)?(?:"
    r"\d{1,2}/\d{1,2}/\d{2,4}"
    r"|\d{4}-\d{1,2}-\d{1,2}"
    r"|(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
    r"jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|"
    r"dec(?:ember)?)\s+\d{1,2}(?:,?\s*\d{2,4})?"
    r")\b",
    re.IGNORECASE,
)

_GAME_TYPE_ALIASES = {
    "pickle": "pickleball",
    "pickleball": "pickleball",
    "progressive": "progressiverummy",
    "progressive rummy": "progressiverummy",
    "progressiverummy": "progressiverummy",
    "gin": "ginrummy",
    "gin rummy": "ginrummy",
    "ginrummy": "ginrummy",
    "phase 10": "phase10",
    "phase10": "phase10",
    "mah jongg": "mahjongg",
    "mahjong": "mahjongg",
    "mahjongg": "mahjongg",
    "dominos": "dominos",
    "dominoes": "dominos",
    "backgammon": "backgammon",
    "cribbage": "cribbage",
    "darts": "darts",
    "cornhole": "cornhole",
}

_PARSE_SYSTEM = """You extract a board-game or sports game result from a user utterance.
Return ONLY a JSON object (no markdown) with this shape:
{
  "mentioned_game_type_code": "pickleball|dominos|progressiverummy|mahjongg|backgammon|ginrummy|cribbage|phase10|darts|cornhole or null",
  "mentioned_group": "group/club name if spoken, else null",
  "mentioned_date": "date string if spoken (any format), else null",
  "score_type": "traditional|rally or null",
  "location_name": "venue/place string or null",
  "sides": [
    {"names": ["Player A", "optional teammate"], "score": 11}
  ]
}
Rules:
- sides are opposing sides; each side may have 1 or 2 names (teammates).
- Prefer Title Case for player names in "names" (Lucas, not lucas).
- scores are integers when spoken; omit score key if unknown.
- Map "rally scoring" / "rally" to score_type "rally"; "traditional" / "side out" to "traditional".
- location_name is a venue or place only (court, house, street, park). Never a group/club name.
- If the user says "in group X" / "for group X", put X in mentioned_group and do NOT use it as location_name.
- If a calendar date is spoken ("on 8/3/2026", "August 3"), put it in mentioned_date.
- If a game name is spoken, put it in mentioned_game_type_code (lowercase codes above).
- Do not invent players or venues not mentioned.
"""


def _title_guest_name(name: str) -> str:
    """Normalize unresolved spoken names for guest display (Lucas, not lucas)."""
    parts = [part for part in (name or "").strip().split() if part]
    if not parts:
        return ""
    return " ".join(part[:1].upper() + part[1:] for part in parts)


def _normalize_game_type_code(raw: str | None) -> str:
    value = (raw or "").strip().lower()
    if not value:
        return ""
    if value in GAME_TYPES:
        return value
    return _GAME_TYPE_ALIASES.get(value, value if value in GAME_TYPES else "")


def _extract_json_object(text: str) -> dict[str, Any]:
    cleaned = (text or "").strip()
    fence = _JSON_FENCE.search(cleaned)
    if fence:
        cleaned = fence.group(1).strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("Could not parse a game draft from the model response.")
    payload = json.loads(cleaned[start : end + 1])
    if not isinstance(payload, dict):
        raise ValueError("Game draft must be a JSON object.")
    return payload


def _resolve_name(group: Group, name: str) -> dict[str, Any]:
    label = (name or "").strip()
    if not label:
        return {
            "player_id": "",
            "guest_name": "",
            "label": "",
            "ambiguous": True,
            "message": "Empty player name.",
        }
    try:
        player = resolve_player_query(group, label)
    except ValueError as exc:
        guest_name = _title_guest_name(label)
        return {
            "player_id": "",
            "guest_name": guest_name,
            "label": guest_name,
            "ambiguous": True,
            "message": str(exc),
        }
    return {
        "player_id": player.pk,
        "guest_name": "",
        "label": player.display_label,
        "ambiguous": False,
        "message": "",
    }


def _resolve_location(
    group: Group,
    *,
    raw_name: str | None,
    user: AbstractBaseUser | None,
    game_type_code: str,
) -> tuple[str, list[str]]:
    warnings: list[str] = []
    mentioned = (raw_name or "").strip()
    if mentioned:
        try:
            location = resolve_location_query(group, mentioned)
            return location.name, warnings
        except ValueError as exc:
            warnings.append(str(exc))
            return mentioned, warnings
    default_name = last_recorded_location_name(user, game_type_code)
    if default_name:
        warnings.append(f"Using last location: {default_name}.")
    return default_name, warnings


def _scope_manual_change_notes(
    *,
    transcript: str,
    raw: dict[str, Any],
    selected_game_type_code: str,
) -> list[str]:
    """Warn when the utterance asks to change fields above AI entry."""
    notes: list[str] = []
    text = transcript or ""

    mentioned_type = _normalize_game_type_code(
        raw.get("mentioned_game_type_code") or raw.get("game_type_code")
    )
    if (
        mentioned_type
        and selected_game_type_code
        and mentioned_type != selected_game_type_code
    ):
        mentioned_name = get_game_type(mentioned_type).name
        notes.append(
            f'Game type "{mentioned_name}" was mentioned but not applied. '
            "Change Game above if needed."
        )

    mentioned_group = str(raw.get("mentioned_group") or "").strip()
    if mentioned_group or _GROUP_HINT.search(text):
        notes.append("Group mentioned is not applied. Change Group above if needed.")

    mentioned_date = str(
        raw.get("mentioned_date") or raw.get("played_on") or ""
    ).strip()
    if mentioned_date or _DATE_HINT.search(text):
        notes.append(
            "Date mentioned is not applied. Change Date played above if needed."
        )

    return notes


def parse_recording_transcript(
    *,
    group: Group,
    transcript: str,
    user: AbstractBaseUser | None,
    model_slug: str,
    default_game_type_code: str = "",
) -> dict[str, Any]:
    """Return a resolved draft for fields below AI entry (not group/game/date)."""
    text = (transcript or "").strip()
    if not text:
        raise ValueError("Transcript is empty.")

    selected_game_type_code = (default_game_type_code or "").strip()
    if selected_game_type_code not in GAME_TYPES:
        raise ValueError("Select a game above first.")

    completion = complete_insight(
        model_slug=model_slug,
        system=_PARSE_SYSTEM,
        user=text,
        max_output_tokens=500,
        temperature=0.1,
    )
    raw = _extract_json_object(completion.text)

    # Locked to the form selection above AI entry.
    game_type_code = selected_game_type_code
    game_type = get_game_type(game_type_code)
    warnings: list[str] = []
    ambiguities = _scope_manual_change_notes(
        transcript=text,
        raw=raw,
        selected_game_type_code=game_type_code,
    )

    score_type = ""
    if game_type_has_score_type(game_type_code):
        mentioned_score_type = (raw.get("score_type") or "").strip()
        if mentioned_score_type:
            score_type = normalize_score_type(game_type_code, mentioned_score_type)
        else:
            score_type = last_recorded_score_type(user, game_type_code) or (
                normalize_score_type(game_type_code, "")
            )
            warnings.append(f"Using score type: {score_type}.")

    location_name, location_warnings = _resolve_location(
        group,
        raw_name=raw.get("location_name"),
        user=user,
        game_type_code=game_type_code,
    )
    warnings.extend(location_warnings)

    sides_raw = raw.get("sides") or []
    if not isinstance(sides_raw, list) or len(sides_raw) < 2:
        raise ValueError("Could not find two sides with scores.")

    sides: list[dict[str, Any]] = []
    for side in sides_raw:
        if not isinstance(side, dict):
            continue
        names = side.get("names") or []
        if isinstance(names, str):
            names = [names]
        names = [str(n).strip() for n in names if str(n).strip()]
        if not names:
            continue
        score = side.get("score")
        try:
            score_int = int(score) if score is not None and score != "" else None
        except (TypeError, ValueError):
            score_int = None
            ambiguities.append(f"Could not read score for {'+'.join(names)}.")
        players = [_resolve_name(group, name) for name in names[:2]]
        for player in players:
            if player.get("ambiguous") and player.get("message"):
                ambiguities.append(player["message"])
        sides.append(
            {
                "score": score_int,
                "players": players,
            }
        )

    if len(sides) < 2:
        raise ValueError("Could not find two sides.")

    return {
        "game_type_code": game_type_code,
        "game_type_name": game_type.name,
        "score_type": score_type,
        "location_name": location_name,
        "sides": sides,
        "warnings": warnings,
        "ambiguities": ambiguities,
        "transcript": text,
    }
