from __future__ import annotations

from django.conf import settings
from openai import OpenAI

from leaderlodge.insights.providers.base import InsightCompletion, InsightProviderError


def complete_openai(
    *,
    model_api_name: str,
    system: str,
    user: str,
    max_output_tokens: int,
    temperature: float,
) -> InsightCompletion:
    api_key = getattr(settings, "OPENAI_API_KEY", "")
    if not api_key:
        raise InsightProviderError("OPENAI_API_KEY is not configured.")

    client = OpenAI(api_key=api_key)
    try:
        response = client.chat.completions.create(
            model=model_api_name,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            max_tokens=max_output_tokens,
            temperature=temperature,
        )
    except Exception as exc:  # noqa: BLE001 - surface provider failures to caller
        raise InsightProviderError(str(exc)) from exc

    choice = response.choices[0].message.content or ""
    usage = response.usage
    return InsightCompletion(
        text=choice.strip(),
        input_tokens=int(usage.prompt_tokens if usage else 0),
        output_tokens=int(usage.completion_tokens if usage else 0),
        model_api_name=model_api_name,
        provider="openai",
    )
