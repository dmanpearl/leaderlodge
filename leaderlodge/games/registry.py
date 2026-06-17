from enum import StrEnum

from dataclasses import dataclass


class ScoreDirection(StrEnum):
    HIGH_WINS = "high"
    LOW_WINS = "low"


@dataclass(frozen=True)
class GameTypeDefinition:
    code: str
    name: str
    min_players: int
    max_players: int
    supports_loser: bool
    score_direction: ScoreDirection
    win_target_score: int | None
    icon_filename: str


def _load_registry() -> dict[str, GameTypeDefinition]:
    return {
        "dominos": GameTypeDefinition(
            code="dominos",
            name="Dominos",
            min_players=2,
            max_players=4,
            supports_loser=False,
            score_direction=ScoreDirection.HIGH_WINS,
            win_target_score=30,
            icon_filename="dominos.png",
        ),
        "progressiverummy": GameTypeDefinition(
            code="progressiverummy",
            name="Progressive Rummy",
            min_players=2,
            max_players=10,
            supports_loser=True,
            score_direction=ScoreDirection.LOW_WINS,
            win_target_score=None,
            icon_filename="progressiverummy.png",
        ),
        "backgammon": GameTypeDefinition(
            code="backgammon",
            name="BackGammon",
            min_players=2,
            max_players=2,
            supports_loser=False,
            score_direction=ScoreDirection.HIGH_WINS,
            win_target_score=None,
            icon_filename="backgammon.png",
        ),
        "mahjongg": GameTypeDefinition(
            code="mahjongg",
            name="Mah Jongg",
            min_players=3,
            max_players=4,
            supports_loser=False,
            score_direction=ScoreDirection.HIGH_WINS,
            win_target_score=None,
            icon_filename="mahjongg.png",
        ),
    }


GAME_TYPES: dict[str, GameTypeDefinition] = _load_registry()


def get_game_type(code: str) -> GameTypeDefinition:
    try:
        return GAME_TYPES[code]
    except KeyError as exc:
        raise ValueError(f"Unknown game type: {code}") from exc


def game_type_choices() -> list[tuple[str, str]]:
    return [(gt.code, gt.name) for gt in GAME_TYPES.values()]
