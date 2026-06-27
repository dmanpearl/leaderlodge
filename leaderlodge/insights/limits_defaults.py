"""
Default insight rate limits.

These values are version-controlled and covered by unit tests. Override at deploy
time via settings.INSIGHTS_LIMITS or per-user via UserProfile.ui_settings
namespace ``insights_limits`` (editable in Django admin).
"""

from __future__ import annotations

from typing import Any

INSIGHT_LIMITS_NAMESPACE = "insights_limits"

# Actor tiers resolved in limits.resolve_actor_tier().
TIER_AUTHENTICATED = "authenticated"
TIER_ANONYMOUS = "anonymous"
TIER_STAFF = "staff"

DEFAULT_INSIGHT_LIMITS: dict[str, Any] = {
    TIER_AUTHENTICATED: {
        "hourly": 30,
        "daily": 100,
    },
    TIER_ANONYMOUS: {
        "hourly": 5,
        "daily": 15,
    },
    TIER_STAFF: {
        "hourly": None,
        "daily": None,
    },
    "global_daily": 5000,
    "models": {
        "flash-lite": {"daily": 100},
        "gpt-4o-mini": {"daily": 40},
        "gemini-flash": {"daily": 20},
    },
}
