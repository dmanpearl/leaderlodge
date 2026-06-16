from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class GameTypeDefinition:
    code: str
    name: str
    min_players: int
    max_players: int
    supports_loser: bool
    icon_filename: str
    validate: Callable


def _load_registry() -> dict[str, GameTypeDefinition]:
    from leaderlodge.games.backgammon import rules as backgammon_rules
    from leaderlodge.games.dominos import rules as dominos_rules
    from leaderlodge.games.mahjongg import rules as mahjongg_rules
    from leaderlodge.games.progressiverummy import rules as progressiverummy_rules

    return {
        "dominos": GameTypeDefinition(
            code="dominos",
            name="Dominos",
            min_players=2,
            max_players=4,
            supports_loser=False,
            icon_filename="dominos.png",
            validate=dominos_rules.validate_game,
        ),
        "progressiverummy": GameTypeDefinition(
            code="progressiverummy",
            name="Progressive Rummy",
            min_players=3,
            max_players=7,
            supports_loser=True,
            icon_filename="progressiverummy.png",
            validate=progressiverummy_rules.validate_game,
        ),
        "backgammon": GameTypeDefinition(
            code="backgammon",
            name="BackGammon",
            min_players=2,
            max_players=2,
            supports_loser=False,
            icon_filename="backgammon.png",
            validate=backgammon_rules.validate_game,
        ),
        "mahjongg": GameTypeDefinition(
            code="mahjongg",
            name="Mah Jongg",
            min_players=3,
            max_players=4,
            supports_loser=False,
            icon_filename="mahjongg.png",
            validate=mahjongg_rules.validate_game,
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
