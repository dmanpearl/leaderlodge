from leaderlodge.insights.registry import (
    DEFAULT_MODEL_SLUG,
    FLASH_LITE,
    GEMINI_FLASH,
    GPT_4O_MINI,
    MODEL_REGISTRY,
    list_model_slugs,
    resolve_model_slug,
)


def test_default_model_is_gpt_4o_mini():
    assert DEFAULT_MODEL_SLUG == GPT_4O_MINI
    assert resolve_model_slug("") == GPT_4O_MINI
    assert resolve_model_slug(None) == GPT_4O_MINI


def test_model_registry_order():
    assert list_model_slugs() == (GPT_4O_MINI, GEMINI_FLASH, FLASH_LITE)
    assert tuple(MODEL_REGISTRY.keys()) == (GPT_4O_MINI, GEMINI_FLASH, FLASH_LITE)
