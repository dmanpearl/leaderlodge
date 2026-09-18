from __future__ import annotations

from typing import Any

from django.utils.dateparse import parse_date

_SCALAR_FIELDS = (
    ("played_on", "played_on"),
    ("score_type", "score_type"),
    ("double_weight", "double_weight"),
    ("half_weight", "half_weight"),
    ("player_count", "player_count"),
)


def _format_played_on(value: Any) -> str:
    if value is None or value == "":
        return "(none)"
    if hasattr(value, "strftime"):
        return value.strftime("%b %d, %Y").replace(" 0", " ")
    parsed = parse_date(str(value))
    if parsed:
        return parsed.strftime("%b %d, %Y").replace(" 0", " ")
    return str(value)


def _format_result(value: Any) -> str:
    if not value:
        return "(none)"
    text = str(value)
    return text[:1].upper() + text[1:]


def _display_value(value: Any) -> str:
    if value is None:
        return "(none)"
    if value == "":
        return "(empty)"
    return str(value)


def _format_scalar_change(label: str, old_value: Any, new_value: Any) -> str:
    return f"{label}: {_display_value(old_value)} to {_display_value(new_value)}"


def _location_name(snapshot: dict[str, Any]) -> str:
    location = snapshot.get("location")
    if not location:
        return "(none)"
    return str(location.get("name") or "(none)")


def _location_pin(snapshot: dict[str, Any]) -> str:
    location = snapshot.get("location")
    if not location:
        return "(none)"
    lat = location.get("lat")
    lon = location.get("lon")
    if lat is None or lon is None:
        return "(none)"
    return f"{lat}, {lon}"


def _participants_by_id(snapshot: dict[str, Any]) -> dict[int, dict[str, Any]]:
    return {
        participant["player_id"]: participant
        for participant in snapshot.get("participants") or []
    }


def _side_label(participants: list[dict[str, Any]]) -> str:
    names = [participant["display_name"] for participant in participants]
    if len(names) == 1:
        return names[0]
    return "+".join(names)


def _group_participants_by_placement(
    participants: list[dict[str, Any]],
) -> list[list[dict[str, Any]]]:
    grouped: dict[Any, list[dict[str, Any]]] = {}
    for participant in participants:
        grouped.setdefault(participant.get("placement"), []).append(participant)
    return [
        sorted(group, key=lambda participant: participant["display_name"])
        for _, group in sorted(
            grouped.items(),
            key=lambda item: (
                item[0] if item[0] is not None else 9999,
                _side_label(item[1]),
            ),
        )
    ]


def _format_lineup_change(
    *,
    prefix: str,
    participant_ids: set[int],
    participants_by_id: dict[int, dict[str, Any]],
) -> list[str]:
    participants = [participants_by_id[player_id] for player_id in participant_ids]
    lines: list[str] = []
    for group in _group_participants_by_placement(participants):
        label = _side_label(group)
        if len(group) == 1:
            lines.append(f"{prefix}: {label}")
        else:
            lines.append(f"{prefix} side: {label}")
    return lines


def format_snapshot_diff(
    old_snapshot: dict[str, Any],
    new_snapshot: dict[str, Any],
) -> str:
    old = old_snapshot or {}
    new = new_snapshot or {}

    if not new:
        lines = ["Game deleted"]
        old_participants = old.get("participants") or []
        if old_participants:
            lines.extend(
                _format_lineup_change(
                    prefix="Removed",
                    participant_ids={
                        participant["player_id"] for participant in old_participants
                    },
                    participants_by_id=_participants_by_id(old),
                )
            )
        return "\n".join(lines)

    lines: list[str] = []

    for field_name, label in _SCALAR_FIELDS:
        old_value = old.get(field_name)
        new_value = new.get(field_name)
        if old_value != new_value:
            lines.append(_format_scalar_change(label, old_value, new_value))

    old_location = _location_name(old)
    new_location = _location_name(new)
    if old_location != new_location:
        lines.append(f"location: {old_location} to {new_location}")
    else:
        old_pin = _location_pin(old)
        new_pin = _location_pin(new)
        if old_pin != new_pin:
            lines.append(f"location pin: {old_pin} to {new_pin}")

    old_by_id = _participants_by_id(old)
    new_by_id = _participants_by_id(new)
    old_ids = set(old_by_id)
    new_ids = set(new_by_id)

    lines.extend(
        _format_lineup_change(
            prefix="Removed",
            participant_ids=old_ids - new_ids,
            participants_by_id=old_by_id,
        )
    )
    lines.extend(
        _format_lineup_change(
            prefix="Added",
            participant_ids=new_ids - old_ids,
            participants_by_id=new_by_id,
        )
    )

    for player_id in sorted(old_ids & new_ids):
        old_participant = old_by_id[player_id]
        new_participant = new_by_id[player_id]
        participant_changes: list[str] = []
        for field_name in ("score", "result", "placement"):
            old_value = old_participant.get(field_name)
            new_value = new_participant.get(field_name)
            if old_value != new_value:
                participant_changes.append(
                    f"{field_name} {_display_value(old_value)} to "
                    f"{_display_value(new_value)}"
                )
        if participant_changes:
            display_name = new_participant["display_name"]
            lines.append(f"{display_name}: {', '.join(participant_changes)}")

    if not lines:
        return "(no differences)"
    return "\n".join(lines)


def format_snapshot_pretty(snapshot: dict[str, Any]) -> str:
    """Human-readable final game state for audit emails."""
    if not snapshot:
        return ""

    lines: list[str] = []

    group = snapshot.get("group") or {}
    group_name = str(group.get("name") or "").strip()
    if group_name:
        lines.append(f"Group: {group_name}")

    game_type_code = str(snapshot.get("game_type_code") or "").strip()
    game_type = None
    if game_type_code:
        try:
            from leaderlodge.games.registry import get_game_type

            game_type = get_game_type(game_type_code)
            lines.append(f"Game: {game_type.name}")
        except Exception:
            lines.append(f"Game: {game_type_code}")

    played_on = snapshot.get("played_on")
    if played_on:
        lines.append(f"Date played: {_format_played_on(played_on)}")

    location = snapshot.get("location") or {}
    location_name = str(location.get("name") or "").strip()
    if location_name:
        location_line = f"Location: {location_name}"
        lat = location.get("lat")
        lon = location.get("lon")
        if lat is not None and lon is not None:
            location_line += f" ({lat}, {lon})"
        lines.append(location_line)

    score_type = str(snapshot.get("score_type") or "").strip()
    if game_type_code and score_type:
        from leaderlodge.games.registry import (
            game_type_has_score_type,
            score_type_label,
        )

        if game_type_has_score_type(game_type_code):
            field_label = (
                game_type.score_type_field_label if game_type else "Score type"
            )
            lines.append(
                f"{field_label}: {score_type_label(game_type_code, score_type)}"
            )

    if snapshot.get("double_weight") == 2:
        lines.append("Game length: Double")
    if snapshot.get("half_weight") == 2:
        lines.append("Game length: Half")

    participants = snapshot.get("participants") or []
    if participants:
        lines.append("")
        lines.append("Results:")
        for side in _group_participants_by_placement(participants):
            if len(side) == 1:
                participant = side[0]
                lines.append(
                    "  "
                    f"{participant['display_name']}: "
                    f"{participant.get('score', '(none)')} "
                    f"({_format_result(participant.get('result'))})"
                )
                continue
            side_label = _side_label(side)
            score_text = " / ".join(
                str(participant.get("score", "")) for participant in side
            )
            result_text = " / ".join(
                _format_result(participant.get("result")) for participant in side
            )
            lines.append(f"  {side_label}: {score_text} ({result_text})")

    return "\n".join(lines)
