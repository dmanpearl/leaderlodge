"""Helpers for inspecting AI request payloads."""

from __future__ import annotations

from typing import Any

from django.contrib.auth.models import AbstractBaseUser, AnonymousUser

from leaderlodge.insights.tools.schemas import ASK_TOOL_SCHEMAS


def insights_debug_allowed(user: AbstractBaseUser | AnonymousUser) -> bool:
    return True
    # Staff-only:
    # return getattr(user, "is_authenticated", False) and (
    #     getattr(user, "is_staff", False) or getattr(user, "is_superuser", False)
    # )


def request_include_debug(
    user: AbstractBaseUser | AnonymousUser,
    payload: dict[str, Any],
) -> bool:
    return bool(payload.get("include_debug")) and insights_debug_allowed(user)


def summarize_ask_tools() -> list[dict[str, str]]:
    tools: list[dict[str, str]] = []
    for schema in ASK_TOOL_SCHEMAS:
        fn = schema.get("function", {})
        tools.append(
            {
                "name": str(fn.get("name", "")),
                "description": str(fn.get("description", "")),
            }
        )
    return tools


def build_contextual_insight_debug(
    *,
    mode: str,
    system_prompt: str,
    context: dict[str, Any],
    preset: str,
    question: str,
    user_message: str,
) -> dict[str, Any]:
    return {
        "mode": mode,
        "system_prompt": system_prompt,
        "user_message": user_message,
        "preset": preset,
        "question": question.strip(),
        "context": context,
    }


def build_ask_insight_debug(
    *,
    question: str,
    user_message: str,
    system_prompt: str,
    scope: dict[str, Any],
    player_roster: list[dict[str, Any]],
    tool_rounds: list[dict[str, Any]],
    tools_used: list[str],
    final_answer: str,
    available_tools: list[dict[str, str]] | None = None,
    llm_messages: list[dict[str, Any]] | None = None,
    note: str = "",
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "mode": "ask",
        "question": question.strip(),
        "initial_user_message": user_message,
        "available_tools": available_tools or summarize_ask_tools(),
        "tool_rounds": tool_rounds,
        "tools_used": tools_used,
        "final_answer": final_answer,
        "system_prompt": system_prompt,
        "scope": scope,
        "player_roster": player_roster,
    }
    if llm_messages is not None:
        payload["llm_messages"] = llm_messages
    if note:
        payload["note"] = note
    return payload
