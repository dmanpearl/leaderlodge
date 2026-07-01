"""Generate insights via LLM with optional response caching."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, replace
from typing import Any

from django.core.cache import cache

from leaderlodge.insights.debug import build_ask_insight_debug, summarize_ask_tools
from leaderlodge.insights.prompts import (
    ASK_SYSTEM_PROMPT,
    GROUP_INSIGHT_SYSTEM_PROMPT,
    MATCHUP_INSIGHT_SYSTEM_PROMPT,
    PLAYER_INSIGHT_SYSTEM_PROMPT,
    PROMPT_VERSION,
    render_ask_user_message,
    render_group_user_message,
    render_matchup_user_message,
    render_user_message,
    resolve_group_preset,
    resolve_matchup_preset,
    resolve_preset,
)
from leaderlodge.insights.registry import resolve_model_slug
from leaderlodge.insights.router import (
    ASK_MAX_OUTPUT_TOKENS,
    ASK_MAX_TOOL_ROUNDS,
    complete_insight,
    complete_with_tools,
)
from leaderlodge.insights.tools.executor import (
    AskScope,
    ToolExecutionError,
    ToolExecutor,
)
from leaderlodge.insights.tools.players import (
    build_ask_player_roster,
    build_question_player_hints,
    question_player_binding_map,
    resolve_question_player_bindings,
)
from leaderlodge.insights.tools.schemas import ASK_TOOL_SCHEMAS

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
    kind: str,
    context: dict[str, Any],
    preset: str,
    question: str,
    model_slug: str,
) -> str:
    payload = {
        "kind": kind,
        "prompt_version": PROMPT_VERSION,
        "model_slug": model_slug,
        "preset": preset,
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
        tab_length=2,
    )


def _generate_insight(
    *,
    kind: str,
    context: dict[str, Any],
    preset: str,
    question: str,
    model_slug: str,
    system_prompt: str,
    user_message: str,
    skip_cache: bool,
) -> InsightResult:
    model = resolve_model_slug(model_slug)
    cache_key = _cache_key(
        kind=kind,
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
        system=system_prompt,
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


@dataclass(frozen=True)
class AskResult(InsightResult):
    tools_used: tuple[str, ...] = ()
    debug: dict[str, Any] | None = None


def _ask_cache_key(
    *,
    scope: AskScope,
    question: str,
    model_slug: str,
) -> str:
    payload = {
        "kind": "ask",
        "prompt_version": PROMPT_VERSION,
        "model_slug": model_slug,
        "question": question.strip(),
        "group_id": scope.group.pk,
        "game_type_code": scope.default_game_type_code,
        "period": scope.period.query_params(),
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return f"{_CACHE_PREFIX}:{digest}"


def generate_ask_response(
    *,
    scope: AskScope,
    question: str,
    model_slug: str,
    period_label: str = "",
    skip_cache: bool = False,
    collect_debug: bool = False,
) -> AskResult:
    model = resolve_model_slug(model_slug)
    cache_key = _ask_cache_key(scope=scope, question=question, model_slug=model)
    cached_payload = None if skip_cache else cache.get(cache_key)
    if isinstance(cached_payload, dict) and cached_payload.get("markdown"):
        return AskResult(
            markdown=cached_payload["markdown"],
            html=cached_payload["html"],
            model_slug=model,
            provider=cached_payload.get("provider", ""),
            prompt_version=PROMPT_VERSION,
            context_schema_version=1,
            cached=True,
            input_tokens=int(cached_payload.get("input_tokens", 0)),
            output_tokens=int(cached_payload.get("output_tokens", 0)),
            tools_used=tuple(cached_payload.get("tools_used", ())),
        )

    player_bindings = resolve_question_player_bindings(scope.group, question)
    scope = replace(
        scope,
        question_player_bindings=question_player_binding_map(player_bindings),
    )
    player_roster = build_ask_player_roster(scope.group)
    user_message = render_ask_user_message(
        question=question,
        group_name=scope.group.name,
        game_type_code=scope.default_game_type_code,
        period_label=period_label,
        player_roster=player_roster,
        player_hints=build_question_player_hints(scope.group, question),
    )
    executor = ToolExecutor(scope)
    messages: list[dict] = [{"role": "user", "content": user_message}]
    tool_rounds: list[dict] = []
    tools_used: list[str] = []
    total_input = 0
    total_output = 0
    provider = ""
    completion = None

    for _round in range(ASK_MAX_TOOL_ROUNDS):
        completion = complete_with_tools(
            model_slug=model,
            system=ASK_SYSTEM_PROMPT,
            messages=messages,
            tools=ASK_TOOL_SCHEMAS,
            max_output_tokens=ASK_MAX_OUTPUT_TOKENS,
        )
        total_input += completion.input_tokens
        total_output += completion.output_tokens
        provider = completion.provider

        if not completion.tool_calls:
            break

        assistant_message: dict = {
            "role": "assistant",
            "content": completion.text or "",
            "tool_calls": [
                {
                    "id": call.id,
                    "type": "function",
                    "function": {
                        "name": call.name,
                        "arguments": json.dumps(call.arguments),
                    },
                }
                for call in completion.tool_calls
            ],
        }
        messages.append(assistant_message)

        round_calls: list[dict] = []
        for call in completion.tool_calls:
            try:
                result = executor.execute(call.name, call.arguments)
            except ToolExecutionError as exc:
                result = {"error": str(exc)}
            tools_used.append(call.name)
            round_calls.append(
                {
                    "tool": call.name,
                    "arguments": call.arguments,
                    "result": result,
                }
            )
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.id,
                    "name": call.name,
                    "content": json.dumps(result),
                }
            )
        tool_rounds.append({"round": len(tool_rounds) + 1, "calls": round_calls})
    else:
        raise ValueError("Ask the Lodge exceeded the tool call limit.")

    if completion is None:
        raise ValueError("Ask the Lodge did not return a response.")

    markdown = completion.text.strip()
    if not markdown:
        raise ValueError("Ask the Lodge returned an empty answer.")

    html = _markdown_to_html(markdown)
    tools_tuple = tuple(tools_used)
    if completion.text:
        messages.append({"role": "assistant", "content": completion.text})

    debug_payload = None
    if collect_debug:
        debug_payload = build_ask_insight_debug(
            question=question,
            user_message=user_message,
            system_prompt=ASK_SYSTEM_PROMPT,
            scope={
                "group_id": scope.group.pk,
                "group_name": scope.group.name,
                "game_type_code": scope.default_game_type_code,
                "period": scope.period.query_params() or {"all_time": True},
                "available_game_types": list(scope.available_game_type_codes),
            },
            player_roster=player_roster,
            tool_rounds=tool_rounds,
            tools_used=list(tools_tuple),
            final_answer=completion.text,
            available_tools=summarize_ask_tools(),
            llm_messages=messages,
        )

    cache.set(
        cache_key,
        {
            "markdown": markdown,
            "html": html,
            "provider": provider,
            "input_tokens": total_input,
            "output_tokens": total_output,
            "tools_used": tools_tuple,
        },
        _CACHE_TTL,
    )
    return AskResult(
        markdown=markdown,
        html=html,
        model_slug=model,
        provider=provider,
        prompt_version=PROMPT_VERSION,
        context_schema_version=1,
        cached=False,
        input_tokens=total_input,
        output_tokens=total_output,
        tools_used=tools_tuple,
        debug=debug_payload,
    )


def generate_player_insight(
    *,
    context: dict[str, Any],
    preset: str,
    question: str = "",
    model_slug: str,
    skip_cache: bool = False,
) -> InsightResult:
    resolved_preset = resolve_preset(preset)
    user_message = render_user_message(
        context=context,
        preset=preset,
        question=question,
    )
    return _generate_insight(
        kind="player",
        context=context,
        preset=resolved_preset,
        question=question,
        model_slug=model_slug,
        system_prompt=PLAYER_INSIGHT_SYSTEM_PROMPT,
        user_message=user_message,
        skip_cache=skip_cache,
    )


def generate_group_insight(
    *,
    context: dict[str, Any],
    preset: str,
    question: str = "",
    model_slug: str,
    skip_cache: bool = False,
) -> InsightResult:
    scope = str(context.get("scope", ""))
    resolved_preset = resolve_group_preset(preset, scope=scope)
    user_message = render_group_user_message(
        context=context,
        preset=preset,
        question=question,
    )
    return _generate_insight(
        kind=f"group:{scope}",
        context=context,
        preset=resolved_preset,
        question=question,
        model_slug=model_slug,
        system_prompt=GROUP_INSIGHT_SYSTEM_PROMPT,
        user_message=user_message,
        skip_cache=skip_cache,
    )


def generate_matchup_insight(
    *,
    context: dict[str, Any],
    preset: str,
    question: str = "",
    model_slug: str,
    skip_cache: bool = False,
) -> InsightResult:
    resolved_preset = resolve_matchup_preset(preset)
    user_message = render_matchup_user_message(
        context=context,
        preset=preset,
        question=question,
    )
    return _generate_insight(
        kind="matchup",
        context=context,
        preset=resolved_preset,
        question=question,
        model_slug=model_slug,
        system_prompt=MATCHUP_INSIGHT_SYSTEM_PROMPT,
        user_message=user_message,
        skip_cache=skip_cache,
    )
