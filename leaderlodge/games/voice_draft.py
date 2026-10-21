"""Parse a spoken or typed game entry into a Record Game draft."""

from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta
from typing import Any

from django.contrib.auth.models import AbstractBaseUser
from django.utils import timezone
from django.utils.dateparse import parse_date

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
from leaderlodge.groups.models import Group, GroupPlayer
from leaderlodge.groups.names import disambiguate_labels
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
_RELATIVE_DATE_OFFSETS: dict[str, int] = {
    "today": 0,
    "yesterday": -1,
    "day before yesterday": -2,
}
_RELATIVE_DATE_HINT = re.compile(
    r"\b(?:date:?\s*)?(?:today|yesterday|day before yesterday)\b",
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
    "mah jong": "mahjongg",
    "maj jongg": "mahjongg",
    "majongg": "mahjongg",
    "mahjong": "mahjongg",
    "mahjongg": "mahjongg",
    "dominos": "dominos",
    "dominoes": "dominos",
    "bones": "dominos",
    "backgammon": "backgammon",
    "cribbage": "cribbage",
    "darts": "darts",
    "cornhole": "cornhole",
}

_PARSE_SYSTEM = """You extract a board-game or sports game result from a user utterance.
Return ONLY a JSON object (no markdown) with this shape:
{
  "mentioned_game_type_code": "pickleball|dominos|progressiverummy|mahjongg|backgammon|ginrummy|cribbage|phase10|darts|cornhole or null",
  "mentioned_game_type_words": "the game-name words copied from the utterance, else null",
  "mentioned_group": "group/club name if spoken, else null",
  "mentioned_date": "date string if spoken (any format), else null",
  "is_half_game": true or false or null,
  "score_type": "traditional|rally|american|chinese_trad|hong_kong|japanese|taiwanese|chinese_mcr or null",
  "location_name": "venue/place string or null",
  "sides": [
    {"names": ["Player A", "optional teammate"], "score": 11}
  ]
}
Rules:
- Always return exactly two opposing sides when two competitors and two scores are present.
- sides are opposing sides; each side may have 1 or 2 names (teammates).
- Prefer Title Case for player names in "names" (Lucas, not lucas).
- scores are integers when spoken; omit score key if unknown.
- Singles with "and" + "to": "Charlene and Nancy M 51 to 45" means two singles sides
  (Charlene score 51, Nancy M score 45). Here "and" separates opponents (like "vs"),
  not teammates. Same for "A and B 11-9" or "A and B 11 to 9 at Venue".
- Teammates only when doubles are clear: "A and B vs C and D", "A plus B 11 vs C plus D 9",
  or explicit team language. Prefer two singles over one doubles side when only two
  names and two scores appear.
- Pickleball score_type: "rally scoring" / "rally" to "rally"; "traditional" / "side out" to "traditional".
- Mah Jongg score_type is regional style: american, chinese_trad (Chinese Traditional),
  hong_kong, japanese (Riichi), taiwanese, chinese_mcr (Chinese Official / MCR).
- location_name is a venue or place only (court, house, street, park). Never a group/club name.
- If the user says "in group X" / "for group X", put X in mentioned_group and do NOT use it as location_name.
- If a calendar date is spoken ("on 8/3/2026", "August 3"), put it in mentioned_date.
- Relative dates ("yesterday", "today") go in mentioned_date using those words.
- If a game name is spoken, set mentioned_game_type_code to that game (lowercase codes above).
  Normalize spelling, nicknames, and misspellings ("maj jongg" and "mahjong" are mahjongg,
  "bones" and "dominoes" are dominos). Copy the words as spoken into mentioned_game_type_words.
  If no game name is spoken, both fields must be null. Never guess a game from scores,
  players, or a game the user did not name.
- Progressive Rummy half game: "half game", "half progressive rummy" -> is_half_game true.
- Do not invent players or venues not mentioned.
"""

_DATE_FORMATS = (
    "%Y-%m-%d",
    "%m/%d/%Y",
    "%m/%d/%y",
    "%B %d, %Y",
    "%b %d, %Y",
    "%B %d %Y",
    "%b %d %Y",
    "%B %d",
    "%b %d",
)

_HALF_GAME_HINT = re.compile(
    r"\bhalf(?:\s+(?:game|progressive(?:\s+rummy)?|rummy))?\b",
    re.IGNORECASE,
)

# "A and B 51 to 45" / "A and B 51-45" when the model wrongly collapses to one side.
_AND_TO_SINGLES = re.compile(
    r"(?P<a>.+?)\s+and\s+(?P<b>.+?)\s+(?P<s1>\d+)\s*(?:to|-)\s*(?P<s2>\d+)\b",
    re.IGNORECASE,
)
_NAME_JOINER = re.compile(r"\b(?:and|vs\.?|versus|plus|with)\b", re.IGNORECASE)
_OPPONENT_SEP = re.compile(r"\b(?:vs\.?|versus)\b", re.IGNORECASE)


def _title_guest_name(name: str) -> str:
    """Normalize unresolved spoken names for guest display (Lucas, not lucas)."""
    parts = [part for part in (name or "").strip().split() if part]
    if not parts:
        return ""
    return " ".join(part[:1].upper() + part[1:] for part in parts)


def _sides_from_and_to_singles(transcript: str) -> list[dict[str, Any]] | None:
    """Recover two singles sides from 'A and B 51 to 45' when the model misses."""
    text = (transcript or "").strip()
    if not text or _OPPONENT_SEP.search(text):
        return None
    match = _AND_TO_SINGLES.search(text)
    if not match:
        return None
    left = match.group("a").strip(" ,.-")
    right = match.group("b").strip(" ,.-")
    if not left or not right:
        return None
    if _NAME_JOINER.search(left) or _NAME_JOINER.search(right):
        return None
    return [
        {"names": [left], "score": int(match.group("s1"))},
        {"names": [right], "score": int(match.group("s2"))},
    ]


def _coerce_two_sides(sides_raw: Any, *, transcript: str) -> list[dict[str, Any]]:
    """Return a two-side list, repairing common 'and ... to' singles phrasing."""
    if isinstance(sides_raw, list) and len(sides_raw) >= 2:
        return sides_raw
    repaired = _sides_from_and_to_singles(transcript)
    if repaired:
        return repaired
    if isinstance(sides_raw, list):
        return sides_raw
    return []


def _normalize_game_type_code(raw: str | None) -> str:
    value = (raw or "").strip().lower()
    if not value:
        return ""
    if value in GAME_TYPES:
        return value
    return _GAME_TYPE_ALIASES.get(value, value if value in GAME_TYPES else "")


def _alias_tokens_for_type(code: str) -> tuple[str, ...]:
    game_type = get_game_type(code)
    tokens = {game_type.name.lower(), code.lower()}
    if game_type.abbr:
        tokens.add(game_type.abbr.lower())
    for alias, alias_code in _GAME_TYPE_ALIASES.items():
        if alias_code == code:
            tokens.add(alias.lower())
    return tuple(sorted(tokens, key=len, reverse=True))


def _detect_mentioned_game_type_heuristic(transcript: str) -> str:
    """Return a game type code when the transcript strongly names a game."""
    text = (transcript or "").lower()
    if not text:
        return ""

    for code in GAME_TYPES:
        for alias in _alias_tokens_for_type(code):
            if not alias:
                continue
            if re.search(rf"\bplaying(?:\s+(?:at|in))?\s+{re.escape(alias)}\b", text):
                return code
            if re.search(rf"\b{re.escape(alias)}\s+game\b", text):
                return code
            if re.search(rf"\ba\s+{re.escape(alias)}\s+game\b", text):
                return code
    return ""


# Words that are not a game name. A model must not use one of these as proof
# that the user named a game.
_NOT_GAME_NAME_WORDS = frozenset(
    {
        "american",
        "chinese",
        "game",
        "half",
        "hong",
        "japanese",
        "kong",
        "playing",
        "rally",
        "today",
        "traditional",
        "taiwanese",
        "versus",
        "yesterday",
    }
)


def _fold_game_text(text: str) -> str:
    """Lowercase, drop apostrophes, and turn hyphens into spaces."""
    folded = (text or "").lower()
    folded = re.sub(r"['\u2019]", "", folded)
    folded = folded.replace("-", " ")
    folded = re.sub(r"[^a-z0-9\s]+", " ", folded)
    return re.sub(r"\s+", " ", folded).strip()


def _squash_game_text(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", _fold_game_text(text))


def _edit_distance(left: str, right: str) -> int:
    if left == right:
        return 0
    if not left:
        return len(right)
    if not right:
        return len(left)
    previous = list(range(len(right) + 1))
    for i, left_char in enumerate(left, start=1):
        current = [i]
        for j, right_char in enumerate(right, start=1):
            insert_cost = current[j - 1] + 1
            delete_cost = previous[j] + 1
            replace_cost = previous[j - 1] + (left_char != right_char)
            current.append(min(insert_cost, delete_cost, replace_cost))
        previous = current
    return previous[-1]


def _close_game_spelling(alias: str, heard: str) -> bool:
    """True when a heard spelling is a small typo of a known game name."""
    left = _squash_game_text(alias)
    right = _squash_game_text(heard)
    if len(left) < 7 or len(right) < 7:
        return False
    if abs(len(left) - len(right)) > 2:
        return False
    return _edit_distance(left, right) <= 2


def _transcript_contains_game_type(transcript: str, code: str) -> bool:
    """True when the utterance names this game, including a close misspelling.

    Short abbreviations are ignored so ordinary words are not read as a game.
    """
    text = _fold_game_text(transcript)
    if not text or code not in GAME_TYPES:
        return False
    words = text.split()
    for alias in _alias_tokens_for_type(code):
        folded_alias = _fold_game_text(alias)
        if len(folded_alias) < 4:
            continue
        if re.search(rf"\b{re.escape(folded_alias)}\b", text):
            return True
        alias_words = folded_alias.split()
        width = len(alias_words)
        if width == 0 or len(words) < width:
            continue
        for start in range(len(words) - width + 1):
            window = " ".join(words[start : start + width])
            if _close_game_spelling(folded_alias, window):
                return True
    return False


def _game_type_named_in_transcript(transcript: str) -> str:
    """Known game name in the utterance, preferring the longest match."""
    text = _fold_game_text(transcript)
    if not text:
        return ""
    words = text.split()
    best_code = ""
    best_length = 0
    tied = False
    for code in GAME_TYPES:
        for alias in _alias_tokens_for_type(code):
            folded_alias = _fold_game_text(alias)
            if len(folded_alias) < 4:
                continue
            matched = bool(re.search(rf"\b{re.escape(folded_alias)}\b", text))
            if not matched:
                alias_words = folded_alias.split()
                width = len(alias_words)
                if width and len(words) >= width:
                    for start in range(len(words) - width + 1):
                        window = " ".join(words[start : start + width])
                        if _close_game_spelling(folded_alias, window):
                            matched = True
                            break
            if not matched:
                continue
            if len(folded_alias) > best_length:
                best_code = code
                best_length = len(folded_alias)
                tied = False
            elif len(folded_alias) == best_length and code != best_code:
                tied = True
    if tied:
        return ""
    return best_code


def _side_names_from_raw(raw: dict[str, Any]) -> set[str]:
    names: set[str] = set()
    for side in raw.get("sides") or []:
        if not isinstance(side, dict):
            continue
        raw_names = side.get("names") or []
        if isinstance(raw_names, str):
            raw_names = [raw_names]
        for name in raw_names:
            folded = _fold_game_text(str(name))
            if not folded:
                continue
            names.add(folded)
            names.update(folded.split())
    return names


def _quoted_game_words_in_transcript(
    transcript: str,
    words: str,
    *,
    side_names: set[str],
) -> bool:
    """True when the model copied a short game-name phrase from the utterance."""
    phrase = _fold_game_text(words)
    if not phrase or phrase in side_names or phrase in _NOT_GAME_NAME_WORDS:
        return False
    tokens = phrase.split()
    if not tokens or len(tokens) > 3:
        return False
    if all(token in side_names or token in _NOT_GAME_NAME_WORDS for token in tokens):
        return False
    text = _fold_game_text(transcript)
    return bool(re.search(rf"\b{re.escape(phrase)}\b", text))


def _resolve_mentioned_game_type(
    *,
    transcript: str,
    raw: dict[str, Any],
) -> tuple[str, str]:
    """Return (game_type_code, source) where source is llm, transcript, heuristic, or empty.

    A model code counts when the utterance contains that game's name, a close
    spelling, a known nickname, or the words the model copied from the utterance.
    A code with none of those is a guess and is ignored. ``game_type_code`` is
    ignored for the same reason.
    """
    llm_code = _normalize_game_type_code(raw.get("mentioned_game_type_code"))
    quoted = str(raw.get("mentioned_game_type_words") or "").strip()
    named = _game_type_named_in_transcript(transcript)
    quoted_ok = _quoted_game_words_in_transcript(
        transcript,
        quoted,
        side_names=_side_names_from_raw(raw),
    )
    if llm_code in GAME_TYPES and (
        _transcript_contains_game_type(transcript, llm_code)
        or (quoted_ok and (not named or named == llm_code))
    ):
        return llm_code, "llm"

    if named in GAME_TYPES:
        return named, "transcript"

    heuristic_code = _detect_mentioned_game_type_heuristic(transcript)
    if heuristic_code in GAME_TYPES:
        return heuristic_code, "heuristic"
    return "", ""


def _parse_relative_date(raw: str) -> date | None:
    value = re.sub(r"^date:?\s*", "", (raw or "").strip(), flags=re.IGNORECASE)
    cleaned = value.strip().lower()
    if not cleaned:
        return None
    offset = _RELATIVE_DATE_OFFSETS.get(cleaned)
    if offset is None:
        return None
    return timezone.localdate() + timedelta(days=offset)


def _parse_spoken_date(raw: str, *, fallback_year: int | None = None) -> date | None:
    value = (raw or "").strip()
    if not value:
        return None

    relative = _parse_relative_date(value)
    if relative:
        return relative

    parsed = parse_date(value)
    if parsed:
        return parsed

    year = fallback_year or timezone.localdate().year
    for fmt in _DATE_FORMATS:
        parse_value = value
        parse_fmt = fmt
        if "%Y" not in fmt and "%y" not in fmt:
            # Python 3.15+ rejects day-of-month formats with no year.
            parse_value = f"{value} {year}"
            parse_fmt = f"{fmt} %Y"
        try:
            return datetime.strptime(parse_value, parse_fmt).date()
        except ValueError:
            continue
    return None


def _resolve_played_on(*, transcript: str, raw: dict[str, Any]) -> str:
    mentioned = str(raw.get("mentioned_date") or raw.get("played_on") or "").strip()
    if mentioned:
        parsed = _parse_spoken_date(mentioned)
        if parsed:
            return parsed.isoformat()

    text = transcript or ""
    relative_match = _RELATIVE_DATE_HINT.search(text)
    if relative_match:
        parsed = _parse_relative_date(relative_match.group(0))
        if parsed:
            return parsed.isoformat()

    match = _DATE_HINT.search(text)
    if match:
        parsed = _parse_spoken_date(match.group(0))
        if parsed:
            return parsed.isoformat()
    return ""


def _transcript_mentions_unresolved_date(
    *,
    transcript: str,
    raw: dict[str, Any],
    played_on: str,
) -> bool:
    if played_on:
        return False
    mentioned = str(raw.get("mentioned_date") or raw.get("played_on") or "").strip()
    if mentioned:
        return True
    text = transcript or ""
    if _DATE_HINT.search(text) or _RELATIVE_DATE_HINT.search(text):
        return True
    return bool(re.search(r"\bdate:?\s*\S", text, re.IGNORECASE))


def _resolve_is_half_game(*, transcript: str, raw: dict[str, Any]) -> bool:
    raw_value = raw.get("is_half_game")
    if raw_value is True:
        return True
    if raw_value is False:
        return False
    if isinstance(raw_value, str):
        cleaned = raw_value.strip().lower()
        if cleaned in {"true", "yes", "1"}:
            return True
        if cleaned in {"false", "no", "0"}:
            return False
    return bool(_HALF_GAME_HINT.search(transcript or ""))


def _build_game_type_conflict(
    *,
    mentioned_code: str,
    selected_code: str,
) -> dict[str, str] | None:
    mentioned_code = _normalize_game_type_code(mentioned_code)
    selected_code = _normalize_game_type_code(selected_code)
    if not mentioned_code or mentioned_code == selected_code:
        return None
    if mentioned_code not in GAME_TYPES or selected_code not in GAME_TYPES:
        return None
    return {
        "mentioned_code": mentioned_code,
        "mentioned_name": get_game_type(mentioned_code).name,
        "selected_code": selected_code,
        "selected_name": get_game_type(selected_code).name,
    }


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


def _apply_disambiguated_side_labels(group: Group, sides: list[dict[str, Any]]) -> None:
    """Replace raw display_label with group-scoped first-name labels.

    Matches Add Player / roster picker so unique names stay "Nancy", not "Nancy M".
    """
    player_ids = [
        player["player_id"]
        for side in sides
        for player in side.get("players") or []
        if player.get("player_id")
    ]
    if not player_ids:
        return

    roster = list(
        GroupPlayer.objects.filter(
            group=group,
            is_active=True,
            is_team=False,
        ).select_related("linked_user")
    )
    by_pk = {player.pk: player for player in roster}
    missing_ids = [pk for pk in set(player_ids) if pk not in by_pk]
    if missing_ids:
        for player in GroupPlayer.objects.filter(pk__in=missing_ids).select_related(
            "linked_user"
        ):
            by_pk[player.pk] = player

    label_map = disambiguate_labels(list(by_pk.values()))
    for side in sides:
        for player in side.get("players") or []:
            player_id = player.get("player_id")
            if player_id and player_id in label_map:
                player["label"] = label_map[player_id]


def _resolve_location(
    group: Group,
    *,
    raw_name: str | None,
    user: AbstractBaseUser | None,
    game_type_code: str,
) -> tuple[str, list[str], str]:
    """Return location name, warnings, and source (spoken, last, or blank)."""
    warnings: list[str] = []
    mentioned = (raw_name or "").strip()
    if mentioned:
        try:
            location = resolve_location_query(group, mentioned)
            return location.name, warnings, "spoken"
        except ValueError as exc:
            warnings.append(str(exc))
            return mentioned, warnings, "spoken"
    default_name = last_recorded_location_name(user, game_type_code, group=group)
    if default_name:
        warnings.append(f"Using last location: {default_name}.")
        return default_name, warnings, "last"
    return "", warnings, ""


def _scope_manual_change_notes(*, transcript: str, raw: dict[str, Any]) -> list[str]:
    """Warn when the utterance asks to change fields we do not apply."""
    notes: list[str] = []
    text = transcript or ""

    mentioned_group = str(raw.get("mentioned_group") or "").strip()
    if mentioned_group or _GROUP_HINT.search(text):
        notes.append("Group mentioned is not applied. Change Group above if needed.")

    return notes


def parse_recording_transcript(
    *,
    group: Group,
    transcript: str,
    user: AbstractBaseUser | None,
    model_slug: str,
    default_game_type_code: str = "",
) -> dict[str, Any]:
    """Return a resolved draft for Record Game fields (group stays manual)."""
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
    ambiguities = _scope_manual_change_notes(transcript=text, raw=raw)

    mentioned_code, _mention_source = _resolve_mentioned_game_type(
        transcript=text,
        raw=raw,
    )
    conflict = _build_game_type_conflict(
        mentioned_code=mentioned_code,
        selected_code=game_type_code,
    )

    played_on = _resolve_played_on(transcript=text, raw=raw)
    if _transcript_mentions_unresolved_date(
        transcript=text,
        raw=raw,
        played_on=played_on,
    ):
        ambiguities.append(
            "Could not resolve the date mentioned. Set Date played manually."
        )
    is_half_game = False
    if game_type.supports_half_game:
        is_half_game = _resolve_is_half_game(transcript=text, raw=raw)

    score_type = ""
    if game_type_has_score_type(game_type_code):
        mentioned_score_type = (raw.get("score_type") or "").strip()
        if mentioned_score_type:
            score_type = normalize_score_type(game_type_code, mentioned_score_type)
        else:
            score_type = last_recorded_score_type(user, game_type_code) or (
                normalize_score_type(game_type_code, "")
            )
            field_label = (game_type.score_type_field_label or "Score type").lower()
            warnings.append(f"Using {field_label}: {score_type}.")

    location_name, location_warnings, location_source = _resolve_location(
        group,
        raw_name=raw.get("location_name"),
        user=user,
        game_type_code=game_type_code,
    )
    warnings.extend(location_warnings)

    sides_raw = _coerce_two_sides(raw.get("sides") or [], transcript=text)
    if len(sides_raw) < 2:
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

    _apply_disambiguated_side_labels(group, sides)

    return {
        "game_type_code": game_type_code,
        "game_type_name": game_type.name,
        "score_type": score_type,
        "location_name": location_name,
        "location_source": location_source,
        "played_on": played_on,
        "is_half_game": is_half_game,
        "sides": sides,
        "warnings": warnings,
        "ambiguities": ambiguities,
        "conflict": conflict,
        "transcript": text,
    }
