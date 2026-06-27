from __future__ import annotations

import json

from django.conf import settings
from openai import OpenAI

from leaderlodge.insights.providers.base import (
    InsightCompletion,
    InsightProviderError,
    ToolCall,
)


def complete_openai(
    *,
    model_api_name: str,
    system: str,
    user: str,
    max_output_tokens: int,
    temperature: float,
) -> InsightCompletion:
    return complete_openai_messages(
        model_api_name=model_api_name,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        tools=None,
        max_output_tokens=max_output_tokens,
        temperature=temperature,
    )


def complete_openai_messages(
    *,
    model_api_name: str,
    messages: list[dict],
    tools: list[dict] | None,
    max_output_tokens: int,
    temperature: float,
) -> InsightCompletion:
    api_key = getattr(settings, "OPENAI_API_KEY", "")
    if not api_key:
        raise InsightProviderError("OPENAI_API_KEY is not configured.")

    client = OpenAI(api_key=api_key)
    kwargs: dict = {
        "model": model_api_name,
        "messages": messages,
        "max_tokens": max_output_tokens,
        "temperature": temperature,
    }
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"

    try:
        response = client.chat.completions.create(**kwargs)
    except Exception as exc:  # noqa: BLE001
        raise InsightProviderError(str(exc)) from exc

    message = response.choices[0].message
    tool_calls: list[ToolCall] = []
    if message.tool_calls:
        for call in message.tool_calls:
            try:
                arguments = json.loads(call.function.arguments or "{}")
            except json.JSONDecodeError:
                arguments = {}
            if not isinstance(arguments, dict):
                arguments = {}
            tool_calls.append(
                ToolCall(
                    id=call.id,
                    name=call.function.name,
                    arguments=arguments,
                )
            )

    usage = response.usage
    assistant_message = {
        "role": "assistant",
        "content": message.content,
    }
    if tool_calls:
        assistant_message["tool_calls"] = [
            {
                "id": call.id,
                "type": "function",
                "function": {
                    "name": call.name,
                    "arguments": json.dumps(call.arguments),
                },
            }
            for call in tool_calls
        ]

    return InsightCompletion(
        text=(message.content or "").strip(),
        input_tokens=int(usage.prompt_tokens if usage else 0),
        output_tokens=int(usage.completion_tokens if usage else 0),
        model_api_name=model_api_name,
        provider="openai",
        tool_calls=tuple(tool_calls),
    )
