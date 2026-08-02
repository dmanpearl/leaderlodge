from django.db.models import Prefetch

from leaderlodge.groups.fuzzy import score_fuzzy_match
from leaderlodge.groups.models import Group, GroupPlayer, GroupTeamMember
from leaderlodge.groups.teams import team_member_players

MAX_PLAYER_SUGGESTIONS = 8
DEFAULT_RECENCY = 1_000_000


def recency_ranks_for_group(
    group: Group, *, game_type_code: str | None = None
) -> dict[int, int]:
    """Map GroupPlayer pk to recency rank (0 = most recently played).

    Pass game_type_code to scope recency to games of that type only, e.g. to
    rank a team by its history in the game currently being recorded rather
    than its most recent game of any type.
    """
    from leaderlodge.games.models import GameParticipantResult

    ranks: dict[int, int] = {}
    next_rank = 0
    results = GameParticipantResult.objects.filter(game__group_id=group.pk)
    if game_type_code:
        results = results.filter(game__game_type_code=game_type_code)
    player_ids = results.order_by(
        "-game__played_on", "-game__created_at", "-game__pk", "pk"
    ).values_list("player_id", flat=True)
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


def _team_entry(
    *, team: GroupPlayer, recency: int, deprioritized: bool = False
) -> dict:
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
        "deprioritized": deprioritized,
    }


def roster_for_group(group: Group, *, game_type_code: str | None = None) -> list[dict]:
    """Roster entries (players and teams) for the player picker.

    Pass game_type_code (the game currently being recorded) to rank teams by
    their history in that specific game type. A team with no games of that
    type is still included (it may be reused for a new game type), but is
    flagged deprioritized so the client sorts it below matching individual
    players/guests instead of letting its recency in other game types win it
    a top suggestion slot.
    """
    recency_ranks = recency_ranks_for_group(group)
    type_recency_ranks = (
        recency_ranks_for_group(group, game_type_code=game_type_code)
        if game_type_code
        else None
    )
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
        if type_recency_ranks is None:
            recency = recency_ranks.get(team.pk, DEFAULT_RECENCY)
            deprioritized = False
        else:
            type_recency = type_recency_ranks.get(team.pk)
            deprioritized = type_recency is None
            recency = type_recency if type_recency is not None else DEFAULT_RECENCY
        entries.append(
            _team_entry(team=team, recency=recency, deprioritized=deprioritized)
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


def search_group_players(
    group: Group, query: str, *, game_type_code: str | None = None
) -> list[dict]:
    query = query.strip()
    if not query:
        return []

    roster = roster_for_group(group, game_type_code=game_type_code)
    scored = []
    for entry in roster:
        best_score = _best_entry_score(query, entry)
        if best_score >= 0:
            scored.append((best_score, entry))

    scored.sort(
        key=lambda item: (
            1 if item[1].get("deprioritized") else 0,
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
