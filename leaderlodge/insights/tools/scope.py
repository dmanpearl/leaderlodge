from __future__ import annotations

from dataclasses import dataclass, field

from leaderlodge.groups.models import Group
from leaderlodge.leaderboards.period import LeaderboardPeriod


@dataclass(frozen=True)
class AskScope:
    group: Group
    period: LeaderboardPeriod
    default_game_type_code: str | None
    available_game_type_codes: tuple[str, ...]
    question_player_bindings: dict[str, int] = field(default_factory=dict)
