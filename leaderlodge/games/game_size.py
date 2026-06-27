"""Game size (player count) filter helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from django.db.models import QuerySet

    from leaderlodge.games.models import Game


def available_game_sizes(games_qs: QuerySet[Game]) -> tuple[int, ...]:
    values = games_qs.values_list("player_count", flat=True).distinct()
    return tuple(sorted({value for value in values if value}))


def resolve_game_size(
    raw: str,
    available: tuple[int, ...] | list[int],
) -> int | None:
    if not raw.isdigit():
        return None
    candidate = int(raw)
    if candidate in available:
        return candidate
    return None


def game_size_filter_label(size: int) -> str:
    return f"{size}-player"
