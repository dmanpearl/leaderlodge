"""Helpers for inspecting AI request payloads."""

from __future__ import annotations

from typing import Any

from django.contrib.auth.models import AbstractBaseUser, AnonymousUser


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
