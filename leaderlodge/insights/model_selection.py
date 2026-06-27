"""Persist preferred insight model in ui_settings."""

from __future__ import annotations

from django.http import HttpRequest

from leaderlodge.accounts.ui_settings import get_ui_settings, set_ui_settings
from leaderlodge.insights.registry import DEFAULT_MODEL_SLUG, resolve_model_slug

INSIGHTS_NAMESPACE = "insights"
MODEL_ID_KEY = "model_id"


def preferred_insight_model_id(request: HttpRequest) -> str:
    if request.user.is_authenticated:
        saved = get_ui_settings(request.user, INSIGHTS_NAMESPACE).get(MODEL_ID_KEY, "")
        if saved:
            return resolve_model_slug(saved)
    return DEFAULT_MODEL_SLUG


def persist_insight_model_id(request: HttpRequest, model_id: str) -> str:
    resolved = resolve_model_slug(model_id)
    if request.user.is_authenticated:
        set_ui_settings(
            request.user,
            INSIGHTS_NAMESPACE,
            {MODEL_ID_KEY: resolved},
        )
    return resolved
