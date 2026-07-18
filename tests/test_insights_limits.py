import pytest
from django.contrib.auth.models import AnonymousUser, User
from django.core.cache import cache
from django.test import RequestFactory, override_settings

from leaderlodge.accounts.ui_settings import set_ui_settings
from leaderlodge.insights.exceptions import InsightRateLimitExceeded
from leaderlodge.insights.limits import (
    INSIGHT_LIMITS_NAMESPACE,
    effective_daily_cap,
    load_site_limit_config,
    resolve_insight_limits,
)
from leaderlodge.insights.limits_defaults import TIER_STAFF
from leaderlodge.insights.rate_limit import (
    check_insight_rate_limit,
    get_usage_status,
    record_insight_usage,
    subject_key,
)


@pytest.fixture
def user(db):
    return User.objects.create_user(username="david", password="test-pass-123")


@pytest.fixture
def staff_user(db):
    return User.objects.create_superuser(
        username="admin",
        email="admin@example.com",
        password="test-pass-123",
    )


@pytest.fixture
def rf():
    return RequestFactory()


@pytest.fixture(autouse=True)
def clear_cache():
    cache.clear()
    yield
    cache.clear()


def _request_for(user=None, ip="203.0.113.10"):
    request = RequestFactory().get("/")
    request.user = user if user is not None else AnonymousUser()
    request.META["REMOTE_ADDR"] = ip
    return request


@pytest.mark.django_db
@override_settings(
    INSIGHTS_LIMITS={"authenticated": {"daily": 200}},
)
def test_settings_override_merges_authenticated_daily():
    config = load_site_limit_config()
    assert config["authenticated"]["daily"] == 200
    assert config["authenticated"]["hourly"] == 30


@pytest.mark.django_db
@override_settings(
    INSIGHTS_LIMITS_JSON='{"global_daily": 999, "models": {"gpt-4o-mini": {"daily": 5}}}',
)
def test_json_env_override_merges():
    config = load_site_limit_config()
    assert config["global_daily"] == 999
    assert config["models"]["gpt-4o-mini"]["daily"] == 5
    assert config["models"]["flash-lite"]["daily"] == 100


@pytest.mark.django_db
def test_user_override_in_ui_settings(user):
    set_ui_settings(
        user,
        INSIGHT_LIMITS_NAMESPACE,
        {
            "hourly": 60,
            "models": {"gemini-flash": {"daily": 3}},
        },
    )
    resolved = resolve_insight_limits(user=user, model_slug="gemini-flash")
    assert resolved.actor.hourly == 60
    assert resolved.model_daily["gemini-flash"] == 3


@pytest.mark.django_db
def test_staff_tier_is_unlimited(staff_user):
    resolved = resolve_insight_limits(user=staff_user, model_slug="gpt-4o-mini")
    assert resolved.tier == TIER_STAFF
    assert resolved.actor.unlimited is False
    assert resolved.actor.hourly is None
    assert resolved.actor.daily is None


@pytest.mark.django_db
def test_effective_daily_cap_uses_tightest(user):
    set_ui_settings(
        user,
        INSIGHT_LIMITS_NAMESPACE,
        {"daily": 50, "models": {"gpt-4o-mini": {"daily": 10}}},
    )
    resolved = resolve_insight_limits(user=user, model_slug="gpt-4o-mini")
    assert effective_daily_cap(resolved) == 10


@pytest.mark.django_db
def test_anonymous_subject_key_uses_ip_hash():
    request = _request_for()
    key = subject_key(request, AnonymousUser())
    assert key.startswith("ip:")
    assert "203.0.113.10" not in key


@pytest.mark.django_db
@override_settings(INSIGHTS_RATE_LIMITS_ENABLED=True)
def test_check_rate_limit_blocks_actor_hourly(user):
    request = _request_for(user)
    for _ in range(30):
        record_insight_usage(request, user=user, model_slug="flash-lite")

    with pytest.raises(InsightRateLimitExceeded) as exc_info:
        check_insight_rate_limit(request, user=user, model_slug="flash-lite")

    assert exc_info.value.scope == "actor"
    assert exc_info.value.window == "hour"
    assert exc_info.value.limit == 30


@pytest.mark.django_db
@override_settings(
    INSIGHTS_RATE_LIMITS_ENABLED=True,
    INSIGHTS_LIMITS={"models": {"gpt-4o-mini": {"daily": 2}}},
)
def test_check_rate_limit_blocks_per_model_daily(user):
    request = _request_for(user)
    for _ in range(2):
        record_insight_usage(request, user=user, model_slug="gpt-4o-mini")

    with pytest.raises(InsightRateLimitExceeded) as exc_info:
        check_insight_rate_limit(request, user=user, model_slug="gpt-4o-mini")

    assert exc_info.value.scope == "model"
    assert exc_info.value.model_slug == "gpt-4o-mini"


@pytest.mark.django_db
@override_settings(
    INSIGHTS_RATE_LIMITS_ENABLED=True, INSIGHTS_LIMITS={"global_daily": 1}
)
def test_global_daily_limit(user):
    request = _request_for(user)
    record_insight_usage(request, user=user, model_slug="flash-lite")

    with pytest.raises(InsightRateLimitExceeded) as exc_info:
        check_insight_rate_limit(request, user=user, model_slug="gpt-4o-mini")

    assert exc_info.value.scope == "global"


@pytest.mark.django_db
@override_settings(INSIGHTS_RATE_LIMITS_ENABLED=True)
def test_get_usage_status_reports_remaining(user):
    request = _request_for(user)
    record_insight_usage(request, user=user, model_slug="flash-lite")

    status = get_usage_status(request, user=user, model_slug="flash-lite")
    actor_hour = next(
        bucket
        for bucket in status.buckets
        if bucket.scope == "actor" and bucket.window == "hour"
    )
    assert actor_hour.used == 1
    assert actor_hour.remaining == 29


@pytest.mark.django_db
@override_settings(INSIGHTS_RATE_LIMITS_ENABLED=True)
def test_user_unlimited_flag(user):
    set_ui_settings(
        user,
        INSIGHT_LIMITS_NAMESPACE,
        {"unlimited": True, "daily": 1},
    )
    resolved = resolve_insight_limits(user=user, model_slug="flash-lite")
    assert resolved.actor.unlimited is True
    assert resolved.actor.daily == 1

    request = _request_for(user)
    for _ in range(5):
        record_insight_usage(request, user=user, model_slug="flash-lite")

    check_insight_rate_limit(request, user=user, model_slug="flash-lite")
