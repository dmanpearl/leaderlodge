"""Generate player insights via LLM with optional response caching."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from django.core.cache import cache

from leaderlodge.insights.prompts import (
    PLAYER_INSIGHT_SYSTEM_PROMPT,
    PROMPT_VERSION,
    render_user_message,
    resolve_preset,
)
from leaderlodge.insights.registry import resolve_model_slug
from leaderlodge.insights.router import complete_insight

_CACHE_PREFIX = "leaderlodge.insights.response"
_CACHE_TTL = 60 * 60 * 24 * 7


@dataclass(frozen=True)
class InsightResult:
    markdown: str
    html: str
    model_slug: str
    provider: str
    prompt_version: int
    context_schema_version: int
    cached: bool
    input_tokens: int
    output_tokens: int


def _cache_key(
    *,
    context: dict[str, Any],
    preset: str,
    question: str,
    model_slug: str,
) -> str:
    payload = {
        "prompt_version": PROMPT_VERSION,
        "model_slug": model_slug,
        "preset": resolve_preset(preset),
        "question": question.strip(),
        "context": context,
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return f"{_CACHE_PREFIX}:{digest}"


def _markdown_to_html(text: str) -> str:
    import markdown

    return markdown.markdown(
        text,
        extensions=["extra", "nl2br", "sane_lists"],
        output_format="html5",
    )


def generate_player_insight(
    *,
    context: dict[str, Any],
    preset: str,
    question: str = "",
    model_slug: str,
    skip_cache: bool = False,
) -> InsightResult:
    model = resolve_model_slug(model_slug)
    user_message = render_user_message(
        context=context,
        preset=preset,
        question=question,
    )
    cache_key = _cache_key(
        context=context,
        preset=preset,
        question=question,
        model_slug=model,
    )
    cached_payload = None if skip_cache else cache.get(cache_key)
    if isinstance(cached_payload, dict) and cached_payload.get("markdown"):
        return InsightResult(
            markdown=cached_payload["markdown"],
            html=cached_payload["html"],
            model_slug=model,
            provider=cached_payload.get("provider", ""),
            prompt_version=PROMPT_VERSION,
            context_schema_version=int(context.get("schema_version", 1)),
            cached=True,
            input_tokens=int(cached_payload.get("input_tokens", 0)),
            output_tokens=int(cached_payload.get("output_tokens", 0)),
        )

    completion = complete_insight(
        model_slug=model,
        system=PLAYER_INSIGHT_SYSTEM_PROMPT,
        user=user_message,
    )
    html = _markdown_to_html(completion.text)
    cache.set(
        cache_key,
        {
            "markdown": completion.text,
            "html": html,
            "provider": completion.provider,
            "input_tokens": completion.input_tokens,
            "output_tokens": completion.output_tokens,
        },
        _CACHE_TTL,
    )
    return InsightResult(
        markdown=completion.text,
        html=html,
        model_slug=model,
        provider=completion.provider,
        prompt_version=PROMPT_VERSION,
        context_schema_version=int(context.get("schema_version", 1)),
        cached=False,
        input_tokens=completion.input_tokens,
        output_tokens=completion.output_tokens,
    )
