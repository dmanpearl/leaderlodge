from __future__ import annotations

import json

from django.conf import settings
from google import genai
from google.genai import types

from leaderlodge.insights.providers.base import (
    InsightCompletion,
    InsightProviderError,
    ToolCall,
)


def complete_google(
    *,
    model_api_name: str,
    system: str,
    user: str,
    max_output_tokens: int,
    temperature: float,
) -> InsightCompletion:
    return complete_google_messages(
        model_api_name=model_api_name,
        messages=[{"role": "user", "content": user}],
        system=system,
        tools=None,
        max_output_tokens=max_output_tokens,
        temperature=temperature,
    )


def _google_function_declarations(tools: list[dict]) -> list[types.FunctionDeclaration]:
    declarations: list[types.FunctionDeclaration] = []
    for tool in tools:
        fn = tool.get("function", {})
        declarations.append(
            types.FunctionDeclaration(
                name=fn.get("name", ""),
                description=fn.get("description", ""),
                parameters=fn.get("parameters") or {"type": "object", "properties": {}},
            )
        )
    return declarations


def complete_google_messages(
    *,
    model_api_name: str,
    messages: list[dict],
    system: str,
    tools: list[dict] | None,
    max_output_tokens: int,
    temperature: float,
) -> InsightCompletion:
    api_key = getattr(settings, "GOOGLE_AI_API_KEY", "")
    if not api_key:
        raise InsightProviderError("GOOGLE_AI_API_KEY is not configured.")

    client = genai.Client(api_key=api_key)
    contents = _google_contents_from_messages(messages)
    config_kwargs: dict = {
        "system_instruction": system,
        "temperature": temperature,
        "max_output_tokens": max_output_tokens,
        "thinking_config": types.ThinkingConfig(thinking_budget=0),
    }
    if tools:
        config_kwargs["tools"] = [
            types.Tool(function_declarations=_google_function_declarations(tools))
        ]

    try:
        response = client.models.generate_content(
            model=model_api_name,
            contents=contents,
            config=types.GenerateContentConfig(**config_kwargs),
        )
    except Exception as exc:  # noqa: BLE001
        raise InsightProviderError(str(exc)) from exc

    text_parts: list[str] = []
    tool_calls: list[ToolCall] = []
    candidate = response.candidates[0] if response.candidates else None
    if candidate and candidate.content and candidate.content.parts:
        for index, part in enumerate(candidate.content.parts):
            if getattr(part, "text", None):
                text_parts.append(part.text)
            function_call = getattr(part, "function_call", None)
            if function_call and function_call.name:
                arguments = dict(function_call.args or {})
                tool_calls.append(
                    ToolCall(
                        id=f"call_{index}",
                        name=function_call.name,
                        arguments=arguments,
                    )
                )

    usage = response.usage_metadata
    input_tokens = int(getattr(usage, "prompt_token_count", 0) or 0)
    output_tokens = int(getattr(usage, "candidates_token_count", 0) or 0)
    thought_tokens = int(getattr(usage, "thoughts_token_count", 0) or 0)
    finish_reason = getattr(candidate, "finish_reason", None) if candidate else None
    if finish_reason and "MAX_TOKENS" in str(finish_reason) and thought_tokens > 0:
        raise InsightProviderError(
            "Gemini response truncated: thinking tokens consumed the output budget. "
            "Try Regenerate or switch models."
        )

    return InsightCompletion(
        text="\n".join(text_parts).strip(),
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        model_api_name=model_api_name,
        provider="google",
        tool_calls=tuple(tool_calls),
    )


def _google_contents_from_messages(messages: list[dict]) -> list[types.Content]:
    contents: list[types.Content] = []
    for message in messages:
        role = message.get("role")
        if role == "tool":
            contents.append(
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_function_response(
                            name=message.get("name", "tool"),
                            response={
                                "result": _parse_tool_content(message.get("content"))
                            },
                        )
                    ],
                )
            )
            continue
        if role == "assistant":
            parts: list[types.Part] = []
            if message.get("content"):
                parts.append(types.Part.from_text(text=str(message["content"])))
            for call in message.get("tool_calls") or []:
                fn = call.get("function", {})
                parts.append(
                    types.Part.from_function_call(
                        name=fn.get("name", ""),
                        args=json.loads(fn.get("arguments") or "{}"),
                    )
                )
            contents.append(types.Content(role="model", parts=parts))
            continue
        if role == "user":
            contents.append(
                types.Content(
                    role="user",
                    parts=[types.Part.from_text(text=str(message.get("content", "")))],
                )
            )
    return contents


def _parse_tool_content(content) -> dict:
    if isinstance(content, dict):
        return content
    if not content:
        return {}
    try:
        parsed = json.loads(str(content))
    except json.JSONDecodeError:
        return {"result": str(content)}
    return parsed if isinstance(parsed, dict) else {"result": parsed}
