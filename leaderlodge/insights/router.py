"""Route insight completion requests to the configured provider."""

from __future__ import annotations

from leaderlodge.insights.providers.base import InsightCompletion, InsightProviderError
from leaderlodge.insights.providers.google import complete_google
from leaderlodge.insights.providers.openai import complete_openai
from leaderlodge.insights.registry import MODEL_REGISTRY, resolve_model_slug

DEFAULT_MAX_OUTPUT_TOKENS = 800
DEFAULT_TEMPERATURE = 0.4


def complete_insight(
    *,
    model_slug: str,
    system: str,
    user: str,
    max_output_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS,
    temperature: float = DEFAULT_TEMPERATURE,
) -> InsightCompletion:
    slug = resolve_model_slug(model_slug)
    model = MODEL_REGISTRY[slug]

    if model.provider == "openai":
        return complete_openai(
            model_api_name=model.api_model,
            system=system,
            user=user,
            max_output_tokens=max_output_tokens,
            temperature=temperature,
        )
    if model.provider == "google":
        return complete_google(
            model_api_name=model.api_model,
            system=system,
            user=user,
            max_output_tokens=max_output_tokens,
            temperature=temperature,
        )
    raise InsightProviderError(f"Unsupported provider: {model.provider}")
