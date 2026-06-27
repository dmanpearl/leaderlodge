from __future__ import annotations

from leaderlodge.groups.models import Group, GroupPlayer


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
    normalized = query.strip()
    if not normalized:
        raise ValueError("A player name or id query is required.")

    players = list(group.players.filter(is_active=True).select_related("linked_user"))
    if not players:
        raise ValueError("This group has no active players.")

    lowered = normalized.lower()
    exact_matches = [
        player
        for player in players
        if any(variant.lower() == lowered for variant in _name_variants(player))
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
            lowered in variant.lower() or variant.lower() in lowered
            for variant in _name_variants(player)
        )
    ]
    if len(partial_matches) == 1:
        return partial_matches[0]
    if len(partial_matches) > 1:
        labels = ", ".join(sorted(player.display_label for player in partial_matches))
        raise ValueError(f"Ambiguous player {query!r}. Matches: {labels}.")

    raise ValueError(f"No player matched {query!r} in this group.")
