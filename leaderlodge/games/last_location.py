"""Last / recent locations for game recording."""

from __future__ import annotations

from django.contrib.auth.models import AbstractBaseUser
from django.db.models import QuerySet

from leaderlodge.games.models import Game
from leaderlodge.games.registry import GAME_TYPES
from leaderlodge.groups.models import Group

# Easy to find and change: how many recent venues the Record Game picker lists.
RECENT_LOCATIONS_LIMIT = 8


def last_recorded_location_name(
    user: AbstractBaseUser | None, game_type_code: str
) -> str:
    if user is None or not user.is_authenticated:
        return ""
    if game_type_code not in GAME_TYPES:
        return ""

    game = (
        Game.objects.filter(
            recorded_by=user,
            game_type_code=game_type_code,
            location__isnull=False,
        )
        .select_related("location")
        .order_by("-played_on", "-created_at", "-pk")
        .first()
    )
    if game is None or game.location is None:
        return ""
    return game.location.name


def _dedupe_location_names(games: QuerySet[Game], *, limit: int) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    # Cap scan so a long history of one venue still finishes quickly.
    for game in games.select_related("location")[: max(limit * 20, limit)]:
        location = game.location
        if location is None:
            continue
        name = location.name
        if not name or name in seen:
            continue
        seen.add(name)
        names.append(name)
        if len(names) >= limit:
            break
    return names


def recent_location_names(
    group: Group,
    *,
    game_type_code: str | None = None,
    limit: int = RECENT_LOCATIONS_LIMIT,
) -> list[str]:
    """Group venues ordered by most recent game at that location.

    Prefers the selected game type when provided, then fills remaining slots
    from the group's full history so the Recent list stays useful for thin types.
    """
    if limit <= 0:
        return []

    base = Game.objects.filter(group=group, location__isnull=False).order_by(
        "-played_on",
        "-created_at",
        "-pk",
    )
    names: list[str] = []
    if game_type_code and game_type_code in GAME_TYPES:
        names = _dedupe_location_names(
            base.filter(game_type_code=game_type_code),
            limit=limit,
        )
    if len(names) < limit:
        fill = _dedupe_location_names(base, limit=limit)
        seen = set(names)
        for name in fill:
            if name in seen:
                continue
            names.append(name)
            seen.add(name)
            if len(names) >= limit:
                break
    return names
