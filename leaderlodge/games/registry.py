from enum import StrEnum

from dataclasses import dataclass

from django.core.exceptions import ValidationError


class ScoreDirection(StrEnum):
    HIGH_WINS = "high"
    LOW_WINS = "low"


class ScoreType(StrEnum):
    TRADITIONAL = "traditional"
    RALLY = "rally"


class MahjonggStyle(StrEnum):
    AMERICAN = "american"
    CHINESE_TRAD = "chinese_trad"
    HONG_KONG = "hong_kong"
    JAPANESE = "japanese"
    TAIWANESE = "taiwanese"
    CHINESE_MCR = "chinese_mcr"


SCORE_TYPE_LABELS: dict[str, str] = {
    ScoreType.TRADITIONAL.value: "Traditional",
    ScoreType.RALLY.value: "Rally",
    MahjonggStyle.AMERICAN.value: "American",
    MahjonggStyle.CHINESE_TRAD.value: "Chinese Traditional",
    MahjonggStyle.HONG_KONG.value: "Hong Kong",
    MahjonggStyle.JAPANESE.value: "Japanese (Riichi)",
    MahjonggStyle.TAIWANESE.value: "Taiwanese",
    MahjonggStyle.CHINESE_MCR.value: "Chinese Official (MCR)",
}

MAHJONGG_STYLE_ICON_FILES: dict[str, str] = {
    MahjonggStyle.AMERICAN.value: "mahjongg-styles/mj-american.png",
    MahjonggStyle.CHINESE_TRAD.value: "mahjongg-styles/mj-chinese-trad.png",
    MahjonggStyle.HONG_KONG.value: "mahjongg-styles/mj-hong-kong.png",
    MahjonggStyle.JAPANESE.value: "mahjongg-styles/mj-japan.png",
    MahjonggStyle.TAIWANESE.value: "mahjongg-styles/mj-taiwan.png",
    MahjonggStyle.CHINESE_MCR.value: "mahjongg-styles/mj-chinese-mcr.png",
}

MAHJONGG_STYLES: tuple[str, ...] = tuple(style.value for style in MahjonggStyle)


@dataclass(frozen=True)
class ShutoutConfig:
    """Per-game-type shutout display (e.g. Pickleball uses label Pickled)."""

    label: str
    icon_filename: str
    # When set, a shutout is every opponent at or under this score (inclusive).
    # When unset, shutouts require every opponent score == 0.
    max_opponent_score: int | None = None
    # When set with max_opponent_score, a double shutout (e.g. double-skunk)
    # is every opponent at or under this lower ceiling.
    double_max_opponent_score: int | None = None


@dataclass(frozen=True)
class GameTypeDefinition:
    code: str
    name: str
    abbr: str
    min_players: int
    max_players: int
    supports_loser: bool
    score_direction: ScoreDirection
    win_target_score: int | None
    icon_filename: str
    # Stored on Game.score_type (pickleball scoring modes, mahjongg styles, etc.).
    score_types: tuple[str, ...] = ()
    default_score_type: str = ""
    score_type_field_label: str = "Score type"
    supports_half_game: bool = False
    rank_uses_score_magnitude: bool = True
    shutout: ShutoutConfig | None = None


def _load_registry() -> dict[str, GameTypeDefinition]:
    return {
        "dominos": GameTypeDefinition(
            code="dominos",
            name="Dominos",
            abbr="DO",
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
            abbr="PR",
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
            abbr="BG",
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
            abbr="MJ",
            min_players=3,
            max_players=4,
            supports_loser=False,
            score_direction=ScoreDirection.HIGH_WINS,
            win_target_score=None,
            icon_filename="mahjongg.png",
            score_types=MAHJONGG_STYLES,
            default_score_type=MahjonggStyle.AMERICAN.value,
            score_type_field_label="Style",
        ),
        "pickleball": GameTypeDefinition(
            code="pickleball",
            name="Pickleball",
            abbr="PB",
            min_players=2,
            max_players=3,
            supports_loser=False,
            score_direction=ScoreDirection.HIGH_WINS,
            win_target_score=None,
            icon_filename="pickleball.png",
            score_types=(ScoreType.TRADITIONAL.value, ScoreType.RALLY.value),
            default_score_type=ScoreType.TRADITIONAL.value,
            rank_uses_score_magnitude=False,
            shutout=ShutoutConfig(label="Pickled", icon_filename="pickle.png"),
        ),
        "ginrummy": GameTypeDefinition(
            code="ginrummy",
            name="Gin Rummy",
            abbr="GR",
            min_players=2,
            max_players=2,
            supports_loser=False,
            score_direction=ScoreDirection.HIGH_WINS,
            win_target_score=None,
            icon_filename="ginrummy.png",
        ),
        "cribbage": GameTypeDefinition(
            code="cribbage",
            name="Cribbage",
            abbr="CR",
            min_players=2,
            max_players=3,
            supports_loser=False,
            score_direction=ScoreDirection.HIGH_WINS,
            win_target_score=121,
            icon_filename="cribbage.png",
            shutout=ShutoutConfig(
                label="Skunked",
                icon_filename="skunk.png",
                max_opponent_score=90,
                double_max_opponent_score=61,
            ),
        ),
        "phase10": GameTypeDefinition(
            code="phase10",
            name="Phase 10",
            abbr="PT",
            min_players=2,
            max_players=6,
            supports_loser=True,
            score_direction=ScoreDirection.LOW_WINS,
            win_target_score=None,
            icon_filename="phase10.png",
        ),
        "darts": GameTypeDefinition(
            code="darts",
            name="Darts",
            abbr="DA",
            min_players=2,
            max_players=3,
            supports_loser=False,
            score_direction=ScoreDirection.HIGH_WINS,
            win_target_score=None,
            icon_filename="darts.png",
        ),
        "cornhole": GameTypeDefinition(
            code="cornhole",
            name="Cornhole",
            abbr="CH",
            min_players=2,
            max_players=2,
            supports_loser=False,
            score_direction=ScoreDirection.HIGH_WINS,
            win_target_score=None,
            icon_filename="cornhole.png",
        ),
    }


GAME_TYPES: dict[str, GameTypeDefinition] = _load_registry()

_ABBR_TO_CODE: dict[str, str] = {gt.abbr.upper(): gt.code for gt in GAME_TYPES.values()}


def get_game_type(code: str) -> GameTypeDefinition:
    try:
        return GAME_TYPES[code]
    except KeyError as exc:
        raise ValueError(f"Unknown game type: {code}") from exc


def game_type_abbr(code: str) -> str:
    """Return the short pill abbreviation for a game type code."""
    return get_game_type(code).abbr


def resolve_game_type_token(token: str) -> str | None:
    """Resolve a full code or abbr to a game type code (case-insensitive)."""
    cleaned = (token or "").strip()
    if not cleaned:
        return None
    lower = cleaned.lower()
    if lower in GAME_TYPES:
        return lower
    return _ABBR_TO_CODE.get(cleaned.upper())


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
        (value, SCORE_TYPE_LABELS.get(value, value)) for value in game_type.score_types
    ]


def score_type_label(code: str, score_type: str) -> str:
    """Human label for a stored score_type / style value."""
    if not game_type_has_score_type(code):
        return ""
    value = normalize_score_type(code, score_type)
    return SCORE_TYPE_LABELS.get(value, value)


def score_type_icon_filename(code: str, score_type: str) -> str:
    """Relative static path under img/game-types/, or empty."""
    if code != "mahjongg":
        return ""
    value = normalize_score_type(code, score_type)
    return MAHJONGG_STYLE_ICON_FILES.get(value, "")


def normalize_score_type(code: str, score_type: str) -> str:
    """Return stored score_type for a game; empty when the type has no score modes."""
    game_type = get_game_type(code)
    if not game_type.score_types:
        return ""
    default = game_type.default_score_type or game_type.score_types[0]
    value = (score_type or "").strip() or default
    valid = set(game_type.score_types)
    if value not in valid:
        labels = ", ".join(sorted(valid))
        field = game_type.score_type_field_label or "Score type"
        raise ValidationError(f"{field} must be one of: {labels}.")
    return value
