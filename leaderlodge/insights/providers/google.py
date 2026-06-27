from __future__ import annotations

from django.conf import settings
from google import genai
from google.genai import types

from leaderlodge.insights.providers.base import InsightCompletion, InsightProviderError


def complete_google(
    *,
    model_api_name: str,
    system: str,
    user: str,
    max_output_tokens: int,
    temperature: float,
) -> InsightCompletion:
    api_key = getattr(settings, "GOOGLE_AI_API_KEY", "")
    if not api_key:
        raise InsightProviderError("GOOGLE_AI_API_KEY is not configured.")

    client = genai.Client(api_key=api_key)
    try:
        response = client.models.generate_content(
            model=model_api_name,
            contents=user,
            config=types.GenerateContentConfig(
                system_instruction=system,
                temperature=temperature,
                max_output_tokens=max_output_tokens,
                # Gemini 2.5+ counts thinking tokens against max_output_tokens.
                # Insights are short summaries; disable reasoning so the full
                # budget is available for visible output.
                thinking_config=types.ThinkingConfig(thinking_budget=0),
            ),
        )
    except Exception as exc:  # noqa: BLE001
        raise InsightProviderError(str(exc)) from exc

    text = (response.text or "").strip()
    usage = response.usage_metadata
    input_tokens = int(getattr(usage, "prompt_token_count", 0) or 0)
    output_tokens = int(getattr(usage, "candidates_token_count", 0) or 0)
    thought_tokens = int(getattr(usage, "thoughts_token_count", 0) or 0)

    candidate = response.candidates[0] if response.candidates else None
    finish_reason = getattr(candidate, "finish_reason", None) if candidate else None
    if finish_reason and "MAX_TOKENS" in str(finish_reason) and thought_tokens > 0:
        raise InsightProviderError(
            "Gemini response truncated: thinking tokens consumed the output budget. "
            "Try Regenerate or switch models."
        )

    return InsightCompletion(
        text=text,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        model_api_name=model_api_name,
        provider="google",
    )
