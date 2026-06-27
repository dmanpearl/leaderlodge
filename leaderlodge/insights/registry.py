"""Curated LLM models exposed in the Insights UI."""

from __future__ import annotations

from dataclasses import dataclass

FLASH_LITE = "flash-lite"
GPT_4O_MINI = "gpt-4o-mini"
GEMINI_FLASH = "gemini-flash"

DEFAULT_MODEL_SLUG = FLASH_LITE


@dataclass(frozen=True)
class InsightModel:
    slug: str
    label: str
    provider: str
    api_model: str


MODEL_REGISTRY: dict[str, InsightModel] = {
    FLASH_LITE: InsightModel(
        slug=FLASH_LITE,
        label="Gemini Flash-Lite",
        provider="google",
        api_model="gemini-2.5-flash-lite",
    ),
    GPT_4O_MINI: InsightModel(
        slug=GPT_4O_MINI,
        label="GPT-4o mini",
        provider="openai",
        api_model="gpt-4o-mini",
    ),
    GEMINI_FLASH: InsightModel(
        slug=GEMINI_FLASH,
        label="Gemini Flash",
        provider="google",
        api_model="gemini-2.5-flash",
    ),
}


def resolve_model_slug(raw: str | None) -> str:
    slug = (raw or "").strip()
    if slug in MODEL_REGISTRY:
        return slug
    return DEFAULT_MODEL_SLUG


def list_model_slugs() -> tuple[str, ...]:
    return tuple(MODEL_REGISTRY.keys())
