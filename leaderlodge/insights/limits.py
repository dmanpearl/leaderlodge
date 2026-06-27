"""Resolve effective insight rate limits (defaults → settings → user override)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from django.conf import settings
from django.contrib.auth.models import AnonymousUser, User

from leaderlodge.accounts.ui_settings import get_ui_settings
from leaderlodge.insights.limits_defaults import (
    DEFAULT_INSIGHT_LIMITS,
    INSIGHT_LIMITS_NAMESPACE,
    TIER_ANONYMOUS,
    TIER_AUTHENTICATED,
    TIER_STAFF,
)
from leaderlodge.insights.registry import list_model_slugs, resolve_model_slug

LimitValue = int | None


@dataclass(frozen=True)
class ModelLimits:
    daily: LimitValue = None


@dataclass(frozen=True)
class ActorLimits:
    hourly: LimitValue = None
    daily: LimitValue = None
    unlimited: bool = False


@dataclass(frozen=True)
class ResolvedInsightLimits:
    actor: ActorLimits
    global_daily: LimitValue
    model_daily: dict[str, LimitValue]
    tier: str
    model_slug: str


def _normalize_limit(value: Any) -> LimitValue:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    if parsed < 0:
        return None
    return parsed


def _merge_actor_limits(
    base: dict[str, Any], override: dict[str, Any]
) -> dict[str, Any]:
    merged = dict(base)
    for key in ("hourly", "daily", "unlimited"):
        if key in override:
            merged[key] = override[key]
    return merged


def _merge_model_limits(
    base: dict[str, Any],
    override: dict[str, Any],
) -> dict[str, Any]:
    merged = {slug: dict(values) for slug, values in base.items()}
    for slug, values in override.items():
        if not isinstance(values, dict):
            continue
        bucket = merged.setdefault(slug, {})
        if "daily" in values:
            bucket["daily"] = values["daily"]
    return merged


def merge_limit_config(
    base: dict[str, Any],
    override: dict[str, Any],
) -> dict[str, Any]:
    """Deep-merge limit config trees (override wins for scalar keys)."""
    if not override:
        return dict(base)

    merged = dict(base)
    for tier in (TIER_AUTHENTICATED, TIER_ANONYMOUS, TIER_STAFF):
        if tier in override:
            merged[tier] = _merge_actor_limits(
                dict(base.get(tier, {})),
                override.get(tier, {}),
            )

    if "global_daily" in override:
        merged["global_daily"] = override["global_daily"]

    if "models" in override:
        merged["models"] = _merge_model_limits(
            dict(base.get("models", {})),
            override.get("models", {}),
        )

    return merged


def load_site_limit_config() -> dict[str, Any]:
    config = dict(DEFAULT_INSIGHT_LIMITS)
    settings_override = getattr(settings, "INSIGHTS_LIMITS", None) or {}
    config = merge_limit_config(config, settings_override)

    raw_json = getattr(settings, "INSIGHTS_LIMITS_JSON", "")
    if raw_json:
        try:
            parsed = json.loads(raw_json)
        except json.JSONDecodeError:
            parsed = {}
        if isinstance(parsed, dict):
            config = merge_limit_config(config, parsed)

    return config


def resolve_actor_tier(user: User | AnonymousUser) -> str:
    if getattr(user, "is_authenticated", False) and (
        getattr(user, "is_staff", False) or getattr(user, "is_superuser", False)
    ):
        return TIER_STAFF
    if getattr(user, "is_authenticated", False):
        return TIER_AUTHENTICATED
    return TIER_ANONYMOUS


def _actor_limits_from_dict(data: dict[str, Any]) -> ActorLimits:
    unlimited = bool(data.get("unlimited"))
    return ActorLimits(
        hourly=_normalize_limit(data.get("hourly")),
        daily=_normalize_limit(data.get("daily")),
        unlimited=unlimited,
    )


def _model_daily_from_config(models_config: dict[str, Any]) -> dict[str, LimitValue]:
    result: dict[str, LimitValue] = {}
    for slug in list_model_slugs():
        bucket = models_config.get(slug, {})
        if isinstance(bucket, dict):
            result[slug] = _normalize_limit(bucket.get("daily"))
        else:
            result[slug] = None
    return result


def resolve_insight_limits(
    *,
    user: User | AnonymousUser,
    model_slug: str | None = None,
) -> ResolvedInsightLimits:
    """
    Effective limits for one request.

    Precedence (later layers override earlier for each field):
    1. DEFAULT_INSIGHT_LIMITS (code)
    2. settings.INSIGHTS_LIMITS / INSIGHTS_LIMITS_JSON (deploy)
    3. UserProfile.ui_settings['insights_limits'] (per user, admin-editable)
    """
    model = resolve_model_slug(model_slug)
    tier = resolve_actor_tier(user)
    config = load_site_limit_config()

    tier_config = dict(config.get(tier, {}))
    if getattr(user, "is_authenticated", False):
        user_override = get_ui_settings(user, INSIGHT_LIMITS_NAMESPACE)
        if user_override:
            tier_config = _merge_actor_limits(tier_config, user_override)
            if "models" in user_override:
                config = merge_limit_config(
                    config,
                    {"models": user_override.get("models", {})},
                )
            if "global_daily" in user_override:
                config["global_daily"] = user_override["global_daily"]

    actor = _actor_limits_from_dict(tier_config)
    global_daily = _normalize_limit(config.get("global_daily"))
    model_daily = _model_daily_from_config(config.get("models", {}))

    return ResolvedInsightLimits(
        actor=actor,
        global_daily=global_daily,
        model_daily=model_daily,
        tier=tier,
        model_slug=model,
    )


def effective_daily_cap(resolved: ResolvedInsightLimits) -> LimitValue:
    """Lowest applicable daily cap for the actor + selected model."""
    if resolved.actor.unlimited:
        model_cap = resolved.model_daily.get(resolved.model_slug)
        caps = [cap for cap in (model_cap, resolved.global_daily) if cap is not None]
        return min(caps) if caps else None

    caps = [
        cap
        for cap in (
            resolved.actor.daily,
            resolved.model_daily.get(resolved.model_slug),
            resolved.global_daily,
        )
        if cap is not None
    ]
    return min(caps) if caps else None
