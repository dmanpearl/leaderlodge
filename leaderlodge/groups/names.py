from django.contrib.auth.models import AbstractBaseUser

_KNOWN_SUFFIXES = frozenset({"jr", "sr", "ii", "iii", "iv"})


def format_user_display_name(user: AbstractBaseUser) -> str:
    first = (user.first_name or "").strip()
    last = (user.last_name or "").strip()
    if first and last:
        return f"{first} {last[0]}"
    if first:
        return first
    return user.get_username()


def _split_suffix(last: str) -> tuple[str, str]:
    """Split trailing name suffix from last name, e.g. 'Smith Jr' to ('Smith', 'Jr')."""
    parts = last.rsplit(None, 1)
    if len(parts) == 2 and parts[1].lower() in _KNOWN_SUFFIXES:
        return parts[0], parts[1]
    return last, ""


def _player_first_last(player) -> tuple[str, str]:
    if player.is_team or not player.linked_user_id or not player.linked_user:
        return "", ""
    first = (player.linked_user.first_name or "").strip()
    last = (player.linked_user.last_name or "").strip()
    return first, last


def _resolve_last_collision(
    first: str,
    base_last: str,
    suffix: str,
    my_pk: int,
    peers: list[int],
    data: dict[int, tuple[str, str]],
) -> str:
    """Find the shortest unique label that disambiguates this player.

    Tries 1, 2, then 3 uppercase chars of the base last name. If all three
    collide (peers share the same 3-char prefix), falls back to the name suffix
    (Jr, Sr, II, etc.) when one is present and unique. Last resort: 3 chars.
    """
    for n in (1, 2, 3):
        my_key = base_last[:n].upper()
        collision = any(
            _split_suffix(data[pk][1])[0][:n].upper() == my_key
            for pk in peers
            if pk != my_pk and data[pk][1]
        )
        if not collision:
            return f"{first} {my_key}"

    if suffix:
        suffix_collision = any(
            _split_suffix(data[pk][1])[1].lower() == suffix.lower()
            for pk in peers
            if pk != my_pk
        )
        if not suffix_collision:
            return f"{first} {suffix}"

    return f"{first} {base_last[:3].upper()}"


def _fallback_label(player) -> str:
    """Label when first-name disambiguation does not apply (guests, etc.)."""
    if getattr(player, "is_team", False):
        return player.display_name
    if player.linked_user_id and player.linked_user:
        return format_user_display_name(player.linked_user)
    return player.display_name


def _disambiguate_labels_in_group(players: list) -> dict[int, str]:
    """Resolve first-name collisions within a single group of non-team players."""
    data: dict[int, tuple[str, str]] = {p.pk: _player_first_last(p) for p in players}

    first_groups: dict[str, list[int]] = {}
    for pk, (first, _) in data.items():
        if first:
            first_groups.setdefault(first.lower(), []).append(pk)

    result: dict[int, str] = {}
    for p in players:
        first, last = data[p.pk]

        if not first:
            result[p.pk] = _fallback_label(p)
            continue

        peers = first_groups.get(first.lower(), [])

        if len(peers) <= 1:
            result[p.pk] = first
            continue

        if not last:
            result[p.pk] = first
            continue

        base_last, suffix = _split_suffix(last)
        result[p.pk] = _resolve_last_collision(
            first, base_last, suffix, p.pk, peers, data
        )

    return result


def _join_team_label(members: list, label_by_pk: dict[int, str]) -> str:
    ordered = sorted(
        members,
        key=lambda player: (label_by_pk[player.pk].lower(), player.pk),
    )
    return "+".join(label_by_pk[player.pk] for player in ordered)


def disambiguate_labels(players: list) -> dict[int, str]:
    """Return {player_id: display label} with first-name collision resolution.

    Collisions are scoped per group: the same first name in different groups
    does not force a last initial.

    Unique first name in the group: show first name only (linked users) or
    stored display_name. Shared first name in the group: show first + 1 to 3
    uppercase chars of last name, then a name suffix (Jr, Sr, II, etc.) if
    needed.

    Team labels are rebuilt from disambiguated member labels so stored names
    like "Nancy M.+Zach" do not keep a last initial when the group has no
    first-name collision.
    """
    from leaderlodge.groups.teams import team_member_players

    expanded: list = []
    seen: set[int] = set()
    teams: list = []
    for player in players:
        if player.pk in seen:
            continue
        seen.add(player.pk)
        expanded.append(player)
        if getattr(player, "is_team", False):
            teams.append(player)

    for team in teams:
        for member in team_member_players(team):
            if member.pk not in seen:
                seen.add(member.pk)
                expanded.append(member)

    by_group: dict[object, list] = {}
    for player in expanded:
        by_group.setdefault(getattr(player, "group_id", None), []).append(player)

    result: dict[int, str] = {}
    for group_players in by_group.values():
        non_teams = [
            player for player in group_players if not getattr(player, "is_team", False)
        ]
        result.update(_disambiguate_labels_in_group(non_teams))

    for team in teams:
        members = team_member_players(team)
        if not members:
            result[team.pk] = team.display_name
            continue
        member_labels = {
            member.pk: result.get(member.pk, _fallback_label(member))
            for member in members
        }
        result[team.pk] = _join_team_label(members, member_labels)

    return result


def apply_label_overrides(players: list) -> None:
    """Disambiguate labels and stamp _label_override on each GroupPlayer instance."""
    label_map = disambiguate_labels(players)
    for player in players:
        player._label_override = label_map[player.pk]
