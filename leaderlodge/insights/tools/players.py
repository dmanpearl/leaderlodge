from __future__ import annotations

import re
from dataclasses import dataclass, field

from leaderlodge.groups.models import Group, GroupPlayer

_COMPARISON_SPLIT = re.compile(
    r"\s+(?:vs\.?|versus|against)\s+",
    re.IGNORECASE,
)
_WORD_TOKEN = re.compile(r"[a-z0-9']+", re.IGNORECASE)


@dataclass(frozen=True)
class QuestionPlayerBinding:
    player_id: int
    display_label: str
    mention: str
    username: str | None = None


def normalize_player_query(query: str) -> str:
    cleaned = query.strip().strip("\"'").strip()
    return cleaned.strip("?.!,")


def _name_variants(player: GroupPlayer) -> set[str]:
    variants = {
        player.display_label.strip(),
        player.display_name.strip(),
    }
    user = player.linked_user
    if user is not None:
        variants.add(user.get_username().strip())
        first = (user.first_name or "").strip()
        last = (user.last_name or "").strip()
        if first:
            variants.add(first)
        if last:
            variants.add(last)
        if first and last:
            variants.add(f"{first} {last}")
            variants.add(f"{first} {last[0]}.")
    return {value for value in variants if value}


def _display_name_variants(player: GroupPlayer) -> set[str]:
    variants = _name_variants(player)
    user = player.linked_user
    if user is not None:
        variants.discard(user.get_username().strip())
    return variants


def _username_for(player: GroupPlayer) -> str | None:
    user = player.linked_user
    if user is None:
        return None
    username = user.get_username().strip()
    return username or None


def _username_matches(query: str, username: str) -> bool:
    lowered_query = query.lower()
    lowered_username = username.lower()
    if lowered_query == lowered_username:
        return True
    return lowered_username.startswith(lowered_query) or lowered_query.startswith(
        lowered_username
    )


def _display_name_matches(query: str, variant: str) -> bool:
    lowered_query = query.lower()
    lowered_variant = variant.lower()
    if lowered_query == lowered_variant:
        return True
    return lowered_query in lowered_variant or lowered_variant in lowered_query


def _segment_query_attempts(segment: str) -> list[str]:
    cleaned = normalize_player_query(segment)
    if not cleaned:
        return []
    attempts = [cleaned]
    for word in reversed(cleaned.split()):
        token = normalize_player_query(word)
        if token and token not in attempts:
            attempts.append(token)
    return attempts


def _add_binding(
    bindings: list[QuestionPlayerBinding],
    seen_ids: set[int],
    *,
    player: GroupPlayer,
    mention: str,
) -> None:
    if player.pk in seen_ids:
        return
    bindings.append(
        QuestionPlayerBinding(
            player_id=player.pk,
            display_label=player.display_label,
            mention=normalize_player_query(mention) or mention.strip(),
            username=_username_for(player),
        )
    )
    seen_ids.add(player.pk)


def resolve_question_player_bindings(
    group: Group,
    question: str,
) -> list[QuestionPlayerBinding]:
    """Resolve players named in the question before the LLM calls tools."""
    roster = build_ask_player_roster(group)
    bindings: list[QuestionPlayerBinding] = []
    seen_ids: set[int] = set()
    lowered_question = question.lower()

    for entry in roster:
        username = entry.get("username")
        if not username or username.lower() not in lowered_question:
            continue
        player = group.players.filter(pk=entry["player_id"], is_active=True).first()
        if player is not None:
            _add_binding(
                bindings,
                seen_ids,
                player=player,
                mention=username,
            )

    for entry in roster:
        for key in ("display_label", "display_name", "first_name", "last_name"):
            value = entry.get(key)
            if not value:
                continue
            token = str(value).lower()
            if re.search(rf"\b{re.escape(token)}\b", lowered_question):
                player = group.players.filter(
                    pk=entry["player_id"], is_active=True
                ).first()
                if player is not None:
                    _add_binding(bindings, seen_ids, player=player, mention=str(value))
                break

    segments = _COMPARISON_SPLIT.split(question)
    if len(segments) > 1:
        for segment in segments:
            for attempt in _segment_query_attempts(segment):
                try:
                    player = resolve_player_query(group, attempt)
                except ValueError:
                    continue
                _add_binding(bindings, seen_ids, player=player, mention=attempt)
                break

    for token in _WORD_TOKEN.findall(question):
        if len(token) < 3:
            continue
        try:
            player = resolve_player_query(group, token)
        except ValueError:
            continue
        _add_binding(bindings, seen_ids, player=player, mention=token)

    return bindings


def question_player_binding_map(
    bindings: list[QuestionPlayerBinding],
) -> dict[str, int]:
    mapping: dict[str, int] = {}
    for binding in bindings:
        keys = {
            normalize_player_query(binding.mention).lower(),
            binding.display_label.lower(),
        }
        if binding.username:
            keys.add(binding.username.lower())
        keys.discard("")
        for key in keys:
            mapping[key] = binding.player_id
    return mapping


def build_question_player_hints(group: Group, question: str) -> str | None:
    bindings = resolve_question_player_bindings(group, question)
    if not bindings:
        return None
    lines = [
        (
            f"- {binding.display_label}: player_id={binding.player_id} "
            f"(question text: {binding.mention})"
        )
        for binding in bindings
    ]
    return (
        "Players mentioned in the question "
        "(pass player_id, or player_a_id / player_b_id, in tool calls):\n"
        + "\n".join(lines)
    )


def build_ask_player_roster(group: Group) -> list[dict]:
    roster: list[dict] = []
    for player in group.players.filter(is_active=True).select_related("linked_user"):
        entry: dict = {
            "player_id": player.pk,
            "display_label": player.display_label,
            "display_name": player.display_name,
        }
        user = player.linked_user
        if user is not None:
            entry["username"] = user.get_username()
            first = (user.first_name or "").strip()
            last = (user.last_name or "").strip()
            if first:
                entry["first_name"] = first
            if last:
                entry["last_name"] = last
        roster.append(entry)
    roster.sort(key=lambda row: str(row["display_label"]).lower())
    return roster


def resolve_player_query(group: Group, query: str) -> GroupPlayer:
    normalized = normalize_player_query(query)
    if not normalized:
        raise ValueError("A player name or id query is required.")

    players = list(group.players.filter(is_active=True).select_related("linked_user"))
    if not players:
        raise ValueError("This group has no active players.")

    lowered = normalized.lower()

    username_matches = [
        player
        for player in players
        if (username := _username_for(player)) is not None
        and _username_matches(lowered, username)
    ]
    if len(username_matches) == 1:
        return username_matches[0]
    if len(username_matches) > 1:
        labels = ", ".join(sorted(player.display_label for player in username_matches))
        raise ValueError(f"Ambiguous player {query!r}. Matches: {labels}.")

    exact_matches = [
        player
        for player in players
        if any(variant.lower() == lowered for variant in _display_name_variants(player))
    ]
    if len(exact_matches) == 1:
        return exact_matches[0]
    if len(exact_matches) > 1:
        labels = ", ".join(sorted(player.display_label for player in exact_matches))
        raise ValueError(f"Ambiguous player {query!r}. Matches: {labels}.")

    if normalized.isdigit():
        player = next((row for row in players if row.pk == int(normalized)), None)
        if player is not None:
            return player

    partial_matches = [
        player
        for player in players
        if any(
            _display_name_matches(lowered, variant)
            for variant in _display_name_variants(player)
        )
    ]
    if len(partial_matches) == 1:
        return partial_matches[0]
    if len(partial_matches) > 1:
        labels = ", ".join(sorted(player.display_label for player in partial_matches))
        raise ValueError(f"Ambiguous player {query!r}. Matches: {labels}.")

    raise ValueError(f"No player matched {query!r} in this group.")
