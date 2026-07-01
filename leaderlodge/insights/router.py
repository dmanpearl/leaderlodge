"""Route insight completion requests to the configured provider."""

from __future__ import annotations

from leaderlodge.insights.providers.base import InsightCompletion, InsightProviderError
from leaderlodge.insights.providers.google import (
    complete_google,
    complete_google_messages,
)
from leaderlodge.insights.providers.openai import (
    complete_openai,
    complete_openai_messages,
)
from leaderlodge.insights.registry import MODEL_REGISTRY, resolve_model_slug

DEFAULT_MAX_OUTPUT_TOKENS = 800
DEFAULT_TEMPERATURE = 0.4
ASK_MAX_OUTPUT_TOKENS = 900
ASK_MAX_TOOL_ROUNDS = 5
ASK_TEMPERATURE = 0.3


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


def complete_with_tools(
    *,
    model_slug: str,
    system: str,
    messages: list[dict],
    tools: list[dict],
    max_output_tokens: int = ASK_MAX_OUTPUT_TOKENS,
    temperature: float = ASK_TEMPERATURE,
) -> InsightCompletion:
    slug = resolve_model_slug(model_slug)
    model = MODEL_REGISTRY[slug]

    if model.provider == "openai":
        payload = [{"role": "system", "content": system}, *messages]
        return complete_openai_messages(
            model_api_name=model.api_model,
            messages=payload,
            tools=tools,
            max_output_tokens=max_output_tokens,
            temperature=temperature,
        )
    if model.provider == "google":
        return complete_google_messages(
            model_api_name=model.api_model,
            messages=messages,
            system=system,
            tools=tools,
            max_output_tokens=max_output_tokens,
            temperature=temperature,
        )
    raise InsightProviderError(f"Unsupported provider: {model.provider}")
