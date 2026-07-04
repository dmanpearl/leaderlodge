from leaderlodge.groups.fuzzy import score_fuzzy_match
from leaderlodge.groups.models import Group, GroupPlayer

MAX_PLAYER_SUGGESTIONS = 8


def roster_for_group(group: Group) -> list[dict]:
    players = group.players.filter(is_active=True, is_team=False).select_related(
        "linked_user"
    )
    entries = []
    for player in players.order_by("display_name"):
        linked_user = player.linked_user
        entries.append(
            {
                "id": player.pk,
                "label": player.display_label,
                "username": linked_user.get_username() if linked_user else None,
                "kind": "member" if linked_user else "guest",
            }
        )
    return entries


def search_group_players(group: Group, query: str) -> list[dict]:
    query = query.strip()
    if not query:
        return []

    roster = roster_for_group(group)
    scored = []
    for entry in roster:
        best_score = score_fuzzy_match(query, entry["label"])
        if entry["username"]:
            best_score = max(best_score, score_fuzzy_match(query, entry["username"]))
        if best_score >= 0:
            scored.append((best_score, entry))

    scored.sort(
        key=lambda item: (-item[0], item[1]["label"].lower()),
    )
    return [entry for _, entry in scored[:MAX_PLAYER_SUGGESTIONS]]


def guest_name_is_available(group: Group, name: str) -> bool:
    cleaned = name.strip()
    if not cleaned:
        return False
    return not group.players.filter(display_name__iexact=cleaned).exists()


def resolve_participant_player(
    *, group: Group, player_id: str | None, guest_name: str | None
) -> GroupPlayer | None:
    from leaderlodge.groups.services import add_guest_player

    if player_id:
        return (
            group.players.filter(pk=player_id, is_active=True, is_team=False)
            .select_related("linked_user")
            .first()
        )

    cleaned = (guest_name or "").strip()
    if not cleaned:
        return None

    existing = group.players.filter(display_name__iexact=cleaned, is_team=False).first()
    if existing is not None:
        return existing

    return add_guest_player(group=group, display_name=cleaned)
