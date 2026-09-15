import pytest

from leaderlodge.games.features import (
    feature_catalog_for_game_type,
    features_for_game_type,
    record_game_feature_fields,
    record_game_kwargs_from_post,
    resolve_feature_selections,
    resolve_feature_selections_from_tool_args,
    resolve_record_game_feature_values,
)


def test_features_for_game_type_returns_type_specific_specs():
    pickleball = features_for_game_type("pickleball")
    assert [feature.key for feature in pickleball] == ["score_type"]
    assert pickleball[0].title == "Score type"

    mahjongg = features_for_game_type("mahjongg")
    assert [feature.key for feature in mahjongg] == ["score_type"]
    assert mahjongg[0].title == "Style"
    assert "japanese" in mahjongg[0].valid_codes()

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

    mahjongg_catalog = feature_catalog_for_game_type("mahjongg")
    assert mahjongg_catalog[0]["title"] == "Style"
    japanese = next(
        value for value in mahjongg_catalog[0]["values"] if value["code"] == "japanese"
    )
    assert "riichi" in japanese["ask_aliases"]

    dominos_catalog = feature_catalog_for_game_type("dominos")
    regular = next(
        value for value in dominos_catalog[0]["values"] if value["code"] == "0"
    )
    assert "normal" in regular["ask_aliases"]
    assert dominos_catalog[0]["title"] == "Game length"


def test_resolve_feature_selections_from_tool_args():
    selections = resolve_feature_selections_from_tool_args(
        {"score_type": "rally"},
        game_type_code="pickleball",
    )
    assert selections == {"score_type": "rally"}

    selections = resolve_feature_selections_from_tool_args(
        {"score_type": "japanese"},
        game_type_code="mahjongg",
    )
    assert selections == {"score_type": "japanese"}

    selections = resolve_feature_selections_from_tool_args(
        {"double_game": True},
        game_type_code="dominos",
    )
    assert selections == {"double_game": "1"}

    selections = resolve_feature_selections_from_tool_args(
        {"half_game": False},
        game_type_code="progressiverummy",
    )
    assert selections == {"half_game": "0"}


def test_record_game_feature_fields_for_score_type_and_half_game():
    pickleball_values = resolve_record_game_feature_values(
        "pickleball",
        last_score_type="rally",
    )
    pickleball_fields = record_game_feature_fields(
        "pickleball", values=pickleball_values
    )
    assert len(pickleball_fields) == 1
    assert pickleball_fields[0]["widget"] == "select"
    assert pickleball_fields[0]["title"] == "Score type"
    assert pickleball_fields[0]["value"] == "rally"
    assert pickleball_fields[0]["select_id"] == "game-score-type"

    mahjongg_fields = record_game_feature_fields(
        "mahjongg",
        values=resolve_record_game_feature_values("mahjongg"),
    )
    assert mahjongg_fields[0]["title"] == "Style"
    assert any(option["code"] == "japanese" for option in mahjongg_fields[0]["options"])

    pr_values = resolve_record_game_feature_values(
        "progressiverummy",
        post_data={"is_half_game": "on"},
    )
    pr_fields = record_game_feature_fields("progressiverummy", values=pr_values)
    assert len(pr_fields) == 1
    assert pr_fields[0]["widget"] == "checkbox"
    assert pr_fields[0]["input_name"] == "is_half_game"
    assert pr_fields[0]["checkbox_id"] == "is-half-game"
    assert pr_fields[0]["checked"] is True
    assert "help_text" not in pr_fields[0]

    assert record_game_feature_fields("dominos", values={}) == []


def test_record_game_kwargs_from_post():
    assert record_game_kwargs_from_post(
        "pickleball",
        {"score_type": "rally"},
    ) == {"score_type": "rally"}
    assert record_game_kwargs_from_post(
        "progressiverummy",
        {"is_half_game": "on"},
    ) == {"half_weight": 2}
    assert record_game_kwargs_from_post("dominos", {}) == {}


def test_resolve_feature_selections_from_tool_args_rejects_invalid():
    with pytest.raises(ValueError, match="score_type must be one of"):
        resolve_feature_selections_from_tool_args(
            {"score_type": "invalid"},
            game_type_code="pickleball",
        )

    with pytest.raises(ValueError, match="double_game must be true or false"):
        resolve_feature_selections_from_tool_args(
            {"double_game": "maybe"},
            game_type_code="dominos",
        )
