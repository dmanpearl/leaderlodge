from django.db.models import Prefetch

from leaderlodge.groups.fuzzy import score_fuzzy_match
from leaderlodge.groups.models import Group, GroupPlayer, GroupTeamMember
from leaderlodge.groups.teams import team_member_players

MAX_PLAYER_SUGGESTIONS = 8
DEFAULT_RECENCY = 1_000_000


def recency_ranks_for_group(group: Group) -> dict[int, int]:
    """Map GroupPlayer pk to recency rank (0 = most recently played)."""
    from leaderlodge.games.models import GameParticipantResult

    ranks: dict[int, int] = {}
    next_rank = 0
    player_ids = (
        GameParticipantResult.objects.filter(game__group_id=group.pk)
        .order_by("-game__played_on", "-game__created_at", "-game__pk", "pk")
        .values_list("player_id", flat=True)
    )
    for player_id in player_ids.iterator():
        if player_id not in ranks:
            ranks[player_id] = next_rank
            next_rank += 1
    return ranks


def _player_entry(*, player: GroupPlayer, recency: int) -> dict:
    linked_user = player.linked_user
    return {
        "id": player.pk,
        "label": player.display_label,
        "username": linked_user.get_username() if linked_user else None,
        "kind": "member" if linked_user else "guest",
        "recency": recency,
    }


def _team_entry(*, team: GroupPlayer, recency: int) -> dict:
    members = team_member_players(team)
    return {
        "id": team.pk,
        "label": team.display_label,
        "username": None,
        "kind": "team",
        "members": [
            _player_entry(
                player=member,
                recency=recency,
            )
            for member in members
        ],
        "recency": recency,
    }


def roster_for_group(group: Group) -> list[dict]:
    recency_ranks = recency_ranks_for_group(group)
    entries: list[dict] = []

    players = group.players.filter(is_active=True, is_team=False).select_related(
        "linked_user"
    )
    for player in players.order_by("display_name"):
        entries.append(
            _player_entry(
                player=player,
                recency=recency_ranks.get(player.pk, DEFAULT_RECENCY),
            )
        )

    teams = (
        group.players.filter(is_active=True, is_team=True)
        .prefetch_related(
            Prefetch(
                "team_members",
                queryset=GroupTeamMember.objects.select_related(
                    "member", "member__linked_user"
                ),
            )
        )
        .order_by("display_name")
    )
    for team in teams:
        if not team_member_players(team):
            continue
        entries.append(
            _team_entry(
                team=team,
                recency=recency_ranks.get(team.pk, DEFAULT_RECENCY),
            )
        )

    return entries


def _best_entry_score(query: str, entry: dict) -> int:
    best_score = score_fuzzy_match(query, entry["label"])
    if entry["username"]:
        best_score = max(best_score, score_fuzzy_match(query, entry["username"]))
    if entry["kind"] == "team":
        for member in entry.get("members") or []:
            best_score = max(best_score, score_fuzzy_match(query, member["label"]))
            if member.get("username"):
                best_score = max(
                    best_score, score_fuzzy_match(query, member["username"])
                )
    return best_score


def search_group_players(group: Group, query: str) -> list[dict]:
    query = query.strip()
    if not query:
        return []

    roster = roster_for_group(group)
    scored = []
    for entry in roster:
        best_score = _best_entry_score(query, entry)
        if best_score >= 0:
            scored.append((best_score, entry))

    scored.sort(
        key=lambda item: (
            -item[0],
            item[1].get("recency", DEFAULT_RECENCY),
            item[1]["label"].lower(),
        ),
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
