"""Game-type feature metadata for filters, forms, and Ask the Lodge.

Capability flags on GameTypeDefinition indicate what exists on the Game model.
This module defines human labels, query param keys, filter bindings, and Ask
aliases for each optional dimension per game type.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from django.db.models import QuerySet


class FeatureBindingKind(StrEnum):
    STRING_FIELD = "string_field"
    WEIGHT_FIELD = "weight_field"


@dataclass(frozen=True)
class GameFeatureValueSpec:
    code: str
    label: str
    ask_aliases: tuple[str, ...] = ()


@dataclass(frozen=True)
class GameFeatureSpec:
    key: str
    title: str
    description: str
    game_type_codes: frozenset[str]
    storage_field: str
    binding_kind: FeatureBindingKind
    values: tuple[GameFeatureValueSpec, ...]
    all_option_label: str = "All"

    def valid_codes(self) -> frozenset[str]:
        return frozenset(value.code for value in self.values)

    def value_label(self, code: str) -> str | None:
        for value in self.values:
            if value.code == code:
                return value.label
        return None


GAME_FEATURES: tuple[GameFeatureSpec, ...] = (
    GameFeatureSpec(
        key="score_type",
        title="Score type",
        description=(
            "Pickleball scoring rules. Traditional uses side-out scoring; "
            "Rally uses rally scoring."
        ),
        game_type_codes=frozenset({"pickleball"}),
        storage_field="score_type",
        binding_kind=FeatureBindingKind.STRING_FIELD,
        values=(
            GameFeatureValueSpec(
                "traditional",
                "Traditional",
                ("traditional", "normal"),
            ),
            GameFeatureValueSpec(
                "rally",
                "Rally",
                ("rally",),
            ),
        ),
    ),
    GameFeatureSpec(
        key="score_type",
        title="Style",
        description=(
            "Mah Jongg regional style (American, Chinese Traditional, Hong Kong, "
            "Japanese Riichi, Taiwanese, Chinese Official MCR)."
        ),
        game_type_codes=frozenset({"mahjongg"}),
        storage_field="score_type",
        binding_kind=FeatureBindingKind.STRING_FIELD,
        values=(
            GameFeatureValueSpec(
                "american",
                "American",
                ("american", "nmjl", "national mah jongg"),
            ),
            GameFeatureValueSpec(
                "chinese_trad",
                "Chinese Traditional",
                ("chinese traditional", "traditional chinese", "chinese trad"),
            ),
            GameFeatureValueSpec(
                "hong_kong",
                "Hong Kong",
                ("hong kong", "hk", "hongkong"),
            ),
            GameFeatureValueSpec(
                "japanese",
                "Japanese (Riichi)",
                ("japanese", "riichi", "japan"),
            ),
            GameFeatureValueSpec(
                "taiwanese",
                "Taiwanese",
                ("taiwanese", "taiwan", "taiwanese 16"),
            ),
            GameFeatureValueSpec(
                "chinese_mcr",
                "Chinese Official (MCR)",
                ("mcr", "chinese official", "chinese mcr", "official"),
            ),
        ),
    ),
    GameFeatureSpec(
        key="double_game",
        title="Game length",
        description=(
            "Dominos games where the winner scored 60 or more count as double "
            "for standings."
        ),
        game_type_codes=frozenset({"dominos"}),
        storage_field="double_weight",
        binding_kind=FeatureBindingKind.WEIGHT_FIELD,
        values=(
            GameFeatureValueSpec(
                "1",
                "Double",
                ("double", "long"),
            ),
            GameFeatureValueSpec(
                "0",
                "Regular",
                ("regular", "normal", "single"),
            ),
        ),
    ),
    GameFeatureSpec(
        key="half_game",
        title="Game length",
        description=(
            "Progressive Rummy games marked as half count as 0.5 games for "
            "standings."
        ),
        game_type_codes=frozenset({"progressiverummy"}),
        storage_field="half_weight",
        binding_kind=FeatureBindingKind.WEIGHT_FIELD,
        values=(
            GameFeatureValueSpec(
                "1",
                "Half",
                ("half",),
            ),
            GameFeatureValueSpec(
                "0",
                "Full",
                ("full",),
            ),
        ),
    ),
)


def features_for_game_type(game_type_code: str) -> tuple[GameFeatureSpec, ...]:
    return tuple(
        feature
        for feature in GAME_FEATURES
        if game_type_code in feature.game_type_codes
    )


# Dominos double games are inferred from scores at save time, not set on Record Game.
RECORD_GAME_CHECKBOX_FEATURES = frozenset({"half_game"})

RECORD_GAME_CHECKBOX_LABELS: dict[str, str] = {
    "half_game": "Half game",
}


def resolve_record_game_feature_values(
    game_type_code: str,
    *,
    post_data=None,
    seeded_score_type: str | None = None,
    last_score_type: str | None = None,
) -> dict[str, str | bool]:
    """Current Record Game feature values for template repopulation."""
    from leaderlodge.games.registry import get_game_type

    game_type = get_game_type(game_type_code)
    values: dict[str, str | bool] = {}

    score_type = ""
    if game_type.score_types:
        score_type = game_type.default_score_type or game_type.score_types[0]
        if seeded_score_type:
            score_type = seeded_score_type
        elif last_score_type:
            score_type = last_score_type

    is_half_game = False
    if post_data is not None:
        if game_type.score_types:
            score_type = post_data.get("score_type", score_type)
        if game_type.supports_half_game:
            is_half_game = "is_half_game" in post_data

    if game_type.score_types:
        values["score_type"] = score_type
    if game_type.supports_half_game:
        values["is_half_game"] = is_half_game
    return values


def record_game_feature_fields(
    game_type_code: str,
    *,
    values: dict[str, str | bool],
) -> list[dict]:
    """Render-ready Record Game fields derived from GAME_FEATURES metadata."""
    from leaderlodge.games.game_type_icons import score_type_icon_url

    rows: list[dict] = []
    for feature in features_for_game_type(game_type_code):
        if feature.binding_kind == FeatureBindingKind.STRING_FIELD:
            selected = str(values.get(feature.key, "") or "")
            options = []
            for value in feature.values:
                options.append(
                    {
                        "code": value.code,
                        "label": value.label,
                        "icon_url": score_type_icon_url(game_type_code, value.code),
                    }
                )
            selected_icon_url = (
                score_type_icon_url(game_type_code, selected) if selected else ""
            )
            select_id = (
                "game-score-type"
                if feature.key == "score_type"
                else f"record-game-{feature.key.replace('_', '-')}"
            )
            rows.append(
                {
                    "key": feature.key,
                    "widget": "select",
                    "title": feature.title,
                    "input_name": feature.key,
                    "select_id": select_id,
                    "value": selected,
                    "icon_url": selected_icon_url,
                    "options": options,
                }
            )
            continue

        if (
            feature.binding_kind == FeatureBindingKind.WEIGHT_FIELD
            and feature.key in RECORD_GAME_CHECKBOX_FEATURES
        ):
            input_name = "is_half_game" if feature.key == "half_game" else feature.key
            checkbox_id = "is-half-game" if feature.key == "half_game" else input_name
            rows.append(
                {
                    "key": feature.key,
                    "widget": "checkbox",
                    "title": RECORD_GAME_CHECKBOX_LABELS.get(
                        feature.key, feature.title
                    ),
                    "input_name": input_name,
                    "checkbox_id": checkbox_id,
                    "checked": bool(values.get(input_name, False)),
                }
            )
    return rows


def record_game_kwargs_from_post(game_type_code: str, post_data) -> dict:
    """Storage kwargs for record_game() from Record Game POST data."""
    from leaderlodge.games.registry import get_game_type, normalize_half_weight

    game_type = get_game_type(game_type_code)
    kwargs: dict = {}
    if game_type.score_types:
        kwargs["score_type"] = post_data.get("score_type", "")
    if game_type.supports_half_game:
        kwargs["half_weight"] = normalize_half_weight(
            is_half="is_half_game" in post_data
        )
    return kwargs


def get_game_feature(key: str, *, game_type_code: str | None = None) -> GameFeatureSpec:
    if game_type_code:
        for feature in features_for_game_type(game_type_code):
            if feature.key == key:
                return feature
    for feature in GAME_FEATURES:
        if feature.key == key:
            return feature
    raise ValueError(f"Unknown game feature: {key}")


def _string_field_filter_kwargs(
    *,
    field: str,
    code: str,
    game_type_code: str,
    storage_field: str,
):
    """Build a Q for string features; default score_type includes legacy blanks."""
    from django.db.models import Q

    from leaderlodge.games.registry import get_game_type

    exact = Q(**{field: code})
    if storage_field != "score_type":
        return exact
    default = get_game_type(game_type_code).default_score_type
    if default and code == default:
        return exact | Q(**{field: ""})
    return exact


def feature_catalog_for_game_type(game_type_code: str) -> list[dict]:
    """JSON-friendly feature metadata for Ask discovery tools."""
    return [
        {
            "key": feature.key,
            "title": feature.title,
            "description": feature.description,
            "all_option_label": feature.all_option_label,
            "values": [
                {
                    "code": value.code,
                    "label": value.label,
                    "ask_aliases": list(value.ask_aliases),
                }
                for value in feature.values
            ],
        }
        for feature in features_for_game_type(game_type_code)
    ]


def shutout_catalog_for_game_type(game_type_code: str) -> dict | None:
    """JSON-friendly shutout metadata for Ask discovery tools."""
    from leaderlodge.games.registry import game_type_shutout_config

    config = game_type_shutout_config(game_type_code)
    if config is None:
        return None

    label = config.label
    label_lower = label.lower()
    aliases = {label_lower, "shutout", "shutouts"}
    if game_type_code == "pickleball":
        aliases.update({"pickle", "pickled", "pickles"})
        description = (
            "When true, only shutout games (one winner, every opponent scored 0). "
            "Active winner phrasing (pickled, shut out): rank by wins. "
            "Passive got pickled is not tracked."
        )
        active = ["pickled", "shut out", "shutout win", "pickled opponents"]
        passive = ["got pickled", "was pickled", "got shut out"]
    elif game_type_code == "cribbage":
        aliases.update(
            {
                "skunk",
                "skunked",
                "skunks",
                "double skunk",
                "double-skunk",
                "double skunked",
            }
        )
        description = (
            "When true, only skunk games (one winner, every opponent at or under "
            "90), including double-skunks (every opponent at or under 61). "
            "Active winner phrasing (skunked, shut out): rank by wins. "
            "Passive got skunked is not tracked."
        )
        active = [
            "skunked",
            "shut out",
            "shutout win",
            "skunked opponents",
            "double skunk",
        ]
        passive = ["got skunked", "was skunked", "got shut out"]
    else:
        description = (
            f"When true, only {label_lower} / shutout games for this type. "
            f"Active winner phrasing: rank by wins. Passive loser-side counts "
            f"are not tracked."
        )
        active = [label_lower, "shut out", "shutout win"]
        passive = [f"got {label_lower}", "got shut out"]

    return {
        "key": "shutout_only",
        "title": label,
        "description": description,
        "grammar": {
            "active_winner": active,
            "passive_loser_not_tracked": passive,
        },
        "ask_aliases": sorted(aliases),
    }


def resolve_feature_selections(
    params,
    *,
    game_type_code: str | None,
) -> dict[str, str]:
    if not game_type_code:
        return {}
    selections: dict[str, str] = {}
    for feature in features_for_game_type(game_type_code):
        raw = (params.get(feature.key) or "").strip()
        if raw in feature.valid_codes():
            selections[feature.key] = raw
    return selections


def feature_summary_labels(
    selections: dict[str, str],
    *,
    game_type_code: str,
) -> list[str]:
    labels: list[str] = []
    for feature in features_for_game_type(game_type_code):
        code = selections.get(feature.key)
        if not code:
            continue
        label = feature.value_label(code)
        if label:
            labels.append(label)
    return labels


def leaderboard_filter_rows(
    *,
    game_type_code: str,
    selections: dict[str, str],
    select_id_prefix: str = "leaderboard",
) -> list[dict]:
    from leaderlodge.games.game_type_icons import score_type_icon_url

    rows: list[dict] = []
    for feature in features_for_game_type(game_type_code):
        options = []
        for value in feature.values:
            option = {"code": value.code, "label": value.label, "icon_url": ""}
            if feature.storage_field == "score_type":
                option["icon_url"] = score_type_icon_url(game_type_code, value.code)
            options.append(option)
        selected = selections.get(feature.key, "")
        selected_icon_url = ""
        if selected and feature.storage_field == "score_type":
            selected_icon_url = score_type_icon_url(game_type_code, selected)
        rows.append(
            {
                "key": feature.key,
                "title": feature.title,
                "select_id": f"{select_id_prefix}-{feature.key.replace('_', '-')}",
                "selected": selected,
                "selected_icon_url": selected_icon_url,
                "all_option_label": feature.all_option_label,
                "options": options,
            }
        )
    return rows


def _weight_value_from_code(code: str) -> int:
    return 2 if code == "1" else 1


def apply_feature_selections_to_games_qs(
    games_qs: QuerySet,
    selections: dict[str, str],
    *,
    game_type_code: str,
) -> QuerySet:
    for feature in features_for_game_type(game_type_code):
        code = selections.get(feature.key)
        if not code:
            continue
        if feature.binding_kind == FeatureBindingKind.STRING_FIELD:
            games_qs = games_qs.filter(
                _string_field_filter_kwargs(
                    field=feature.storage_field,
                    code=code,
                    game_type_code=game_type_code,
                    storage_field=feature.storage_field,
                )
            )
        elif feature.binding_kind == FeatureBindingKind.WEIGHT_FIELD:
            games_qs = games_qs.filter(
                **{feature.storage_field: _weight_value_from_code(code)}
            )
    return games_qs


def _normalize_weight_tool_arg(raw: object) -> str | None:
    if isinstance(raw, bool):
        return "1" if raw else "0"
    text = str(raw).strip().lower()
    if text in {"1", "true", "yes"}:
        return "1"
    if text in {"0", "false", "no"}:
        return "0"
    return None


def resolve_feature_selections_from_tool_args(
    arguments: dict,
    *,
    game_type_code: str,
) -> dict[str, str]:
    """Resolve Ask tool args to feature selection codes; raises ValueError."""
    selections: dict[str, str] = {}
    errors: list[str] = []
    for feature in features_for_game_type(game_type_code):
        if feature.key not in arguments:
            continue
        raw = arguments.get(feature.key)
        if raw is None:
            continue
        if feature.binding_kind == FeatureBindingKind.STRING_FIELD:
            code = str(raw).strip()
            if code not in feature.valid_codes():
                valid = ", ".join(sorted(feature.valid_codes()))
                errors.append(f"{feature.key} must be one of: {valid}.")
            else:
                selections[feature.key] = code
            continue
        code = _normalize_weight_tool_arg(raw)
        if code is None or code not in feature.valid_codes():
            errors.append(
                f"{feature.key} must be true or false "
                f"(double/regular or half/full for {feature.title})."
            )
        else:
            selections[feature.key] = code
    if errors:
        raise ValueError(" ".join(errors))
    return selections


def game_features_response_payload(
    selections: dict[str, str],
    *,
    game_type_code: str,
) -> dict:
    if not selections:
        return {}
    return {
        "game_features": [
            {
                "key": feature.key,
                "title": feature.title,
                "value_code": selections[feature.key],
                "value_label": feature.value_label(selections[feature.key]),
            }
            for feature in features_for_game_type(game_type_code)
            if feature.key in selections
        ]
    }


def apply_feature_selections_to_results_qs(
    results_qs: QuerySet,
    selections: dict[str, str],
    *,
    game_type_code: str,
) -> QuerySet:
    for feature in features_for_game_type(game_type_code):
        code = selections.get(feature.key)
        if not code:
            continue
        field = f"game__{feature.storage_field}"
        if feature.binding_kind == FeatureBindingKind.STRING_FIELD:
            results_qs = results_qs.filter(
                _string_field_filter_kwargs(
                    field=field,
                    code=code,
                    game_type_code=game_type_code,
                    storage_field=feature.storage_field,
                )
            )
        elif feature.binding_kind == FeatureBindingKind.WEIGHT_FIELD:
            results_qs = results_qs.filter(**{field: _weight_value_from_code(code)})
    return results_qs


def selections_to_leaderboard_fields(
    selections: dict[str, str],
) -> dict[str, str | bool | None]:
    """Map URL selections to LeaderboardGameFilters-friendly values."""
    score_type = selections.get("score_type")
    double_game: bool | None = None
    half_game: bool | None = None
    if "double_game" in selections:
        double_game = selections["double_game"] == "1"
    if "half_game" in selections:
        half_game = selections["half_game"] == "1"
    return {
        "score_type": score_type,
        "double_game": double_game,
        "half_game": half_game,
    }


def leaderboard_fields_to_selections(
    *,
    score_type: str | None = None,
    double_game: bool | None = None,
    half_game: bool | None = None,
) -> dict[str, str]:
    selections: dict[str, str] = {}
    if score_type:
        selections["score_type"] = score_type
    if double_game is True:
        selections["double_game"] = "1"
    elif double_game is False:
        selections["double_game"] = "0"
    if half_game is True:
        selections["half_game"] = "1"
    elif half_game is False:
        selections["half_game"] = "0"
    return selections
