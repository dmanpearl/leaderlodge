import pytest

from leaderlodge.games.features import (
    feature_catalog_for_game_type,
    features_for_game_type,
    resolve_feature_selections,
)


def test_features_for_game_type_returns_type_specific_specs():
    pickleball = features_for_game_type("pickleball")
    assert [feature.key for feature in pickleball] == ["score_type"]

    dominos = features_for_game_type("dominos")
    assert [feature.key for feature in dominos] == ["double_game"]

    progressiverummy = features_for_game_type("progressiverummy")
    assert [feature.key for feature in progressiverummy] == ["half_game"]

    assert features_for_game_type("backgammon") == ()


def test_resolve_feature_selections_ignores_irrelevant_params():
    selections = resolve_feature_selections(
        {"score_type": "rally", "double_game": "1", "half_game": "1"},
        game_type_code="dominos",
    )
    assert selections == {"double_game": "1"}


def test_feature_catalog_includes_ask_aliases():
    catalog = feature_catalog_for_game_type("pickleball")
    assert catalog[0]["key"] == "score_type"
    traditional = next(
        value for value in catalog[0]["values"] if value["code"] == "traditional"
    )
    assert "normal" in traditional["ask_aliases"]

    dominos_catalog = feature_catalog_for_game_type("dominos")
    regular = next(
        value for value in dominos_catalog[0]["values"] if value["code"] == "0"
    )
    assert "normal" in regular["ask_aliases"]
    assert dominos_catalog[0]["title"] == "Game length"
