from leaderlodge.games.ai_entry_copy import ai_entry_example, ai_entry_help_content
from leaderlodge.games.registry import GAME_TYPES


def test_ai_entry_example_covers_every_registered_game_type():
    for code in GAME_TYPES:
        example = ai_entry_example(code)
        assert example
        assert example.endswith("in Santa Monica")


def test_ai_entry_examples_are_game_type_specific():
    pickleball = ai_entry_example("pickleball")
    mahjongg = ai_entry_example("mahjongg")
    progressive = ai_entry_example("progressiverummy")
    dominos = ai_entry_example("dominos")

    assert "rally scoring" in pickleball
    assert "American style" in mahjongg
    assert "half game" in progressive
    assert "rally" not in dominos
    assert "style" not in dominos
    assert "half game" not in dominos


def test_ai_entry_help_mentions_type_specific_topics():
    pickleball = ai_entry_help_content("pickleball")
    mahjongg = ai_entry_help_content("mahjongg")
    progressive = ai_entry_help_content("progressiverummy")
    dominos = ai_entry_help_content("dominos")

    assert "score type" in pickleball
    assert "Example: " in pickleball
    assert "rally scoring, in Santa Monica" in pickleball

    assert "style" in mahjongg
    assert "American style" in mahjongg
    assert "half game" in progressive
    assert "score type" not in dominos
    assert "style" not in dominos
    assert "half game" not in dominos
