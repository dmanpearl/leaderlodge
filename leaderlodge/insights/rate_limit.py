"""Cache-backed insight rate limit enforcement."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Literal

from django.contrib.auth.models import AnonymousUser, User
from django.core.cache import cache
from django.http import HttpRequest
from django.utils import timezone

from leaderlodge.insights.exceptions import InsightRateLimitExceeded
from leaderlodge.insights.limits import (
    LimitValue,
    ResolvedInsightLimits,
    resolve_insight_limits,
)
from leaderlodge.insights.registry import resolve_model_slug

Window = Literal["hour", "day"]
Scope = Literal["global", "actor", "model"]

_CACHE_PREFIX = "leaderlodge.insights.usage"
_HOUR_TTL = 60 * 60 * 2
_DAY_TTL = 60 * 60 * 48


def insight_rate_limits_enabled() -> bool:
    from django.conf import settings

    return getattr(settings, "INSIGHTS_RATE_LIMITS_ENABLED", False)


@dataclass(frozen=True)
class UsageBucket:
    scope: Scope
    window: Window
    limit: int
    used: int
    remaining: int | None
    model_slug: str | None = None

    @property
    def label(self) -> str:
        if self.scope == "global":
            return "site"
        if self.scope == "model" and self.model_slug:
            return f"model:{self.model_slug}"
        return "you"


@dataclass(frozen=True)
class InsightUsageStatus:
    model_slug: str
    tier: str
    buckets: tuple[UsageBucket, ...]

    def tightest_bucket(self) -> UsageBucket | None:
        limited = [bucket for bucket in self.buckets if bucket.limit is not None]
        if not limited:
            return None
        return min(limited, key=lambda bucket: bucket.remaining or 0)


def _client_ip(request: HttpRequest) -> str:
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "") or "unknown"


def subject_key(request: HttpRequest, user: User | AnonymousUser) -> str:
    if getattr(user, "is_authenticated", False):
        return f"user:{user.pk}"
    ip = _client_ip(request)
    digest = hashlib.sha256(ip.encode("utf-8")).hexdigest()[:16]
    return f"ip:{digest}"


def _window_token(window: Window) -> str:
    now = timezone.localtime(timezone.now())
    if window == "hour":
        return now.strftime("%Y%m%d%H")
    return now.strftime("%Y%m%d")


def _cache_key(
    *, subject: str, scope: Scope, window: Window, token: str, model_slug: str = ""
) -> str:
    parts = [_CACHE_PREFIX, subject, scope, window, token]
    if model_slug:
        parts.append(model_slug)
    return ":".join(parts)


def _ttl_for_window(window: Window) -> int:
    return _HOUR_TTL if window == "hour" else _DAY_TTL


def _get_count(key: str, *, window: Window) -> int:
    value = cache.get(key)
    if value is None:
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _increment(key: str, *, window: Window) -> int:
    ttl = _ttl_for_window(window)
    if cache.add(key, 1, ttl):
        return 1
    try:
        return cache.incr(key)
    except ValueError:
        cache.set(key, 1, ttl)
        return 1


def _retry_after_seconds(window: Window) -> int:
    now = timezone.localtime(timezone.now())
    if window == "hour":
        seconds_into_hour = (now.minute * 60) + now.second
        return max(1, 3600 - seconds_into_hour)
    seconds_into_day = (now.hour * 3600) + (now.minute * 60) + now.second
    return max(1, 86400 - seconds_into_day)


def _check_bucket(
    *,
    subject: str,
    scope: Scope,
    window: Window,
    limit: LimitValue,
    model_slug: str = "",
) -> UsageBucket | None:
    if limit is None:
        return None

    token = _window_token(window)
    key = _cache_key(
        subject=subject,
        scope=scope,
        window=window,
        token=token,
        model_slug=model_slug,
    )
    used = _get_count(key, window=window)
    remaining = max(0, limit - used)
    bucket = UsageBucket(
        scope=scope,
        window=window,
        limit=limit,
        used=used,
        remaining=remaining,
        model_slug=model_slug or None,
    )
    if used >= limit:
        raise InsightRateLimitExceeded(
            scope=scope,
            limit=limit,
            window=window,
            retry_after_seconds=_retry_after_seconds(window),
            model_slug=model_slug or None,
        )
    return bucket


def _applicable_buckets(
    *,
    subject: str,
    resolved: ResolvedInsightLimits,
) -> list[tuple[Scope, Window, LimitValue, str]]:
    checks: list[tuple[Scope, Window, LimitValue, str]] = []
    if resolved.global_daily is not None:
        checks.append(("global", "day", resolved.global_daily, ""))

    if not resolved.actor.unlimited:
        if resolved.actor.hourly is not None:
            checks.append(("actor", "hour", resolved.actor.hourly, ""))
        if resolved.actor.daily is not None:
            checks.append(("actor", "day", resolved.actor.daily, ""))

    model_daily = resolved.model_daily.get(resolved.model_slug)
    if model_daily is not None:
        checks.append(("model", "day", model_daily, resolved.model_slug))

    return checks


def get_usage_status(
    request: HttpRequest,
    *,
    user: User | AnonymousUser,
    model_slug: str | None = None,
) -> InsightUsageStatus:
    model = resolve_model_slug(model_slug)
    resolved = resolve_insight_limits(user=user, model_slug=model)
    subject = subject_key(request, user)
    buckets: list[UsageBucket] = []

    for scope, window, limit, model_part in _applicable_buckets(
        subject=subject,
        resolved=resolved,
    ):
        token = _window_token(window)
        key = _cache_key(
            subject=subject if scope != "global" else "global",
            scope=scope,
            window=window,
            token=token,
            model_slug=model_part,
        )
        used = _get_count(key, window=window)
        buckets.append(
            UsageBucket(
                scope=scope,
                window=window,
                limit=limit,
                used=used,
                remaining=max(0, limit - used),
                model_slug=model_part or None,
            )
        )

    return InsightUsageStatus(
        model_slug=model,
        tier=resolved.tier,
        buckets=tuple(buckets),
    )


def check_insight_rate_limit(
    request: HttpRequest,
    *,
    user: User | AnonymousUser,
    model_slug: str | None = None,
) -> ResolvedInsightLimits:
    """Raise InsightRateLimitExceeded when any applicable bucket is full."""
    model = resolve_model_slug(model_slug)
    resolved = resolve_insight_limits(user=user, model_slug=model)
    if not insight_rate_limits_enabled():
        return resolved

    subject = subject_key(request, user)

    for scope, window, limit, model_part in _applicable_buckets(
        subject=subject,
        resolved=resolved,
    ):
        _check_bucket(
            subject=subject if scope != "global" else "global",
            scope=scope,
            window=window,
            limit=limit,
            model_slug=model_part,
        )

    return resolved


def record_insight_usage(
    request: HttpRequest,
    *,
    user: User | AnonymousUser,
    model_slug: str | None = None,
) -> None:
    """Increment all applicable counters after a successful insight generation."""
    if not insight_rate_limits_enabled():
        return

    model = resolve_model_slug(model_slug)
    resolved = resolve_insight_limits(user=user, model_slug=model)
    subject = subject_key(request, user)

    for scope, window, limit, model_part in _applicable_buckets(
        subject=subject,
        resolved=resolved,
    ):
        if limit is None:
            continue
        key = _cache_key(
            subject=subject if scope != "global" else "global",
            scope=scope,
            window=window,
            token=_window_token(window),
            model_slug=model_part,
        )
        _increment(key, window=window)
