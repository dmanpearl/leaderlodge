"""Last / recent locations for game recording."""

from __future__ import annotations

from django.contrib.auth.models import AbstractBaseUser
from django.db.models import QuerySet

from leaderlodge.games.models import Game
from leaderlodge.games.registry import GAME_TYPES
from leaderlodge.groups.models import Group

# Easy to find and change: how many recent venues the Record Game picker lists.
RECENT_LOCATIONS_LIMIT = 8


def _group_id(group: Group | int | str | None) -> int | None:
    if group is None or group == "":
        return None
    if isinstance(group, Group):
        return group.pk
    if isinstance(group, int):
        return group
    if isinstance(group, str) and group.isdigit():
        return int(group)
    return None


def last_recorded_location_name(
    user: AbstractBaseUser | None,
    game_type_code: str,
    group: Group | int | str | None = None,
) -> str:
    """Venue on the game this user most recently saved for the type.

    Sorted by save time, so a back-dated entry still becomes the default
    for the next Record Game. ``group`` limits the search to that group.
    """
    if user is None or not user.is_authenticated:
        return ""
    if game_type_code not in GAME_TYPES:
        return ""

    games = Game.objects.filter(
        recorded_by=user,
        game_type_code=game_type_code,
        location__isnull=False,
    )
    group_id = _group_id(group)
    if group_id is not None:
        games = games.filter(group_id=group_id)

    game = games.select_related("location").order_by("-created_at", "-pk").first()
    if game is None or game.location is None:
        return ""
    return game.location.name


def last_recorded_score_type(user: AbstractBaseUser | None, game_type_code: str) -> str:
    """Prior score_type / style for this user and type (e.g. rally, american)."""
    from leaderlodge.games.registry import (
        game_type_has_score_type,
        normalize_score_type,
    )

    if user is None or not user.is_authenticated:
        return ""
    if not game_type_has_score_type(game_type_code):
        return ""

    game = (
        Game.objects.filter(recorded_by=user, game_type_code=game_type_code)
        .order_by("-played_on", "-created_at", "-pk")
        .first()
    )
    if game is None:
        return ""
    return normalize_score_type(game_type_code, game.score_type or "")


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
