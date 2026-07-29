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

_FEATURES_BY_KEY: dict[str, GameFeatureSpec] = {
    feature.key: feature for feature in GAME_FEATURES
}


def features_for_game_type(game_type_code: str) -> tuple[GameFeatureSpec, ...]:
    return tuple(
        feature
        for feature in GAME_FEATURES
        if game_type_code in feature.game_type_codes
    )


def get_game_feature(key: str) -> GameFeatureSpec:
    try:
        return _FEATURES_BY_KEY[key]
    except KeyError as exc:
        raise ValueError(f"Unknown game feature: {key}") from exc


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
    rows: list[dict] = []
    for feature in features_for_game_type(game_type_code):
        rows.append(
            {
                "key": feature.key,
                "title": feature.title,
                "select_id": f"{select_id_prefix}-{feature.key.replace('_', '-')}",
                "selected": selections.get(feature.key, ""),
                "all_option_label": feature.all_option_label,
                "options": [
                    {"code": value.code, "label": value.label}
                    for value in feature.values
                ],
            }
        )
    return rows


def _weight_value_from_code(code: str) -> int:
    return 2 if code == "1" else 1


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
            results_qs = results_qs.filter(**{field: code})
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
