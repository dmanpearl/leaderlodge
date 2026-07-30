from enum import StrEnum

from dataclasses import dataclass

from django.core.exceptions import ValidationError


class ScoreDirection(StrEnum):
    HIGH_WINS = "high"
    LOW_WINS = "low"


class ScoreType(StrEnum):
    TRADITIONAL = "traditional"
    RALLY = "rally"


SCORE_TYPE_LABELS: dict[ScoreType, str] = {
    ScoreType.TRADITIONAL: "Traditional",
    ScoreType.RALLY: "Rally",
}


@dataclass(frozen=True)
class ShutoutConfig:
    """Per-game-type shutout display (e.g. Pickleball uses label Pickled)."""

    label: str
    icon_filename: str


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
    score_types: tuple[ScoreType, ...] = ()
    supports_half_game: bool = False
    rank_uses_score_magnitude: bool = True
    shutout: ShutoutConfig | None = None


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
            supports_half_game=True,
        ),
        "backgammon": GameTypeDefinition(
            code="backgammon",
            name="Backgammon",
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
        "pickleball": GameTypeDefinition(
            code="pickleball",
            name="Pickleball",
            min_players=2,
            max_players=3,
            supports_loser=False,
            score_direction=ScoreDirection.HIGH_WINS,
            win_target_score=None,
            icon_filename="pickleball.png",
            score_types=(ScoreType.TRADITIONAL, ScoreType.RALLY),
            rank_uses_score_magnitude=False,
            shutout=ShutoutConfig(label="Pickled", icon_filename="pickle.png"),
        ),
    }


GAME_TYPES: dict[str, GameTypeDefinition] = _load_registry()


def get_game_type(code: str) -> GameTypeDefinition:
    try:
        return GAME_TYPES[code]
    except KeyError as exc:
        raise ValueError(f"Unknown game type: {code}") from exc


def score_direction_label(code: str) -> str:
    """Return low_wins or high_wins for prompts and API payloads."""
    game_type = get_game_type(code)
    if game_type.score_direction == ScoreDirection.LOW_WINS:
        return "low_wins"
    return "high_wins"


def scoring_interpretation_note(code: str) -> str | None:
    """Short note for Ask tool JSON when raw point totals invert usual meaning."""
    if score_direction_label(code) == "low_wins":
        return (
            "Applies to raw game points only (total_points, min_score, max_score), "
            "not rank_score. Compare average points per game (avg_points_display), "
            "not raw totals alone. Lower total_points and per-game scores are better. "
            "More points means worse scoring, not better. "
            "rank_score is always higher-is-better regardless of game type."
        )
    return None


def game_type_choices() -> list[tuple[str, str]]:
    return [(gt.code, gt.name) for gt in GAME_TYPES.values()]


def game_type_has_score_type(code: str) -> bool:
    return bool(get_game_type(code).score_types)


def game_type_supports_half_game(code: str) -> bool:
    return get_game_type(code).supports_half_game


def game_type_rank_uses_score_magnitude(code: str) -> bool:
    return get_game_type(code).rank_uses_score_magnitude


def game_type_supports_shutout(code: str) -> bool:
    return get_game_type(code).shutout is not None


def game_type_shutout_config(code: str) -> ShutoutConfig | None:
    return get_game_type(code).shutout


def normalize_half_weight(*, is_half: bool) -> int:
    return 2 if is_half else 1


def score_type_choices_for(code: str) -> list[tuple[str, str]]:
    game_type = get_game_type(code)
    return [
        (score_type.value, SCORE_TYPE_LABELS[score_type])
        for score_type in game_type.score_types
    ]


def normalize_score_type(code: str, score_type: str) -> str:
    """Return stored score_type for a game; empty when the type has no score modes."""
    game_type = get_game_type(code)
    if not game_type.score_types:
        return ""
    value = (score_type or "").strip() or ScoreType.TRADITIONAL.value
    valid = {item.value for item in game_type.score_types}
    if value not in valid:
        labels = ", ".join(sorted(valid))
        raise ValidationError(f"Score type must be one of: {labels}.")
    return value
