import json
from unittest.mock import patch

import pytest
from django.contrib.auth.models import User
from django.test import override_settings
from django.urls import reverse

from leaderlodge.groups.services import add_guest_player, create_group_with_owner
from leaderlodge.insights.context.group import (
    SCOPE_HALL_OF_FAME,
    SCOPE_LEADERBOARD,
    SCHEMA_VERSION,
    build_group_insight_context,
)
from leaderlodge.insights.service import InsightResult
from leaderlodge.leaderboards.period import LeaderboardPeriod
from tests.test_games import _load_roster_post, _save_game_post


@pytest.fixture
def user(db):
    return User.objects.create_user(username="david", password="test-pass-123")


@pytest.fixture
def group(user):
    group = create_group_with_owner(user=user, name="Dom Club")
    add_guest_player(group=group, display_name="Pat")
    add_guest_player(group=group, display_name="Alex")
    return group


def _mock_group_insight_result(**overrides):
    defaults = {
        "markdown": "## Overview\n\nPat leads the board.",
        "html": "<h2>Overview</h2><p>Pat leads the board.</p>",
        "model_slug": "flash-lite",
        "provider": "google",
        "prompt_version": 3,
        "context_schema_version": SCHEMA_VERSION,
        "cached": False,
        "input_tokens": 100,
        "output_tokens": 50,
    }
    defaults.update(overrides)
    return InsightResult(**defaults)


@pytest.mark.django_db
def test_build_leaderboard_insight_context(client, user, group):
    client.force_login(user)
    client.post(reverse("games:create"), _load_roster_post(group))
    client.post(reverse("games:create"), _save_game_post(group))

    context = build_group_insight_context(
        group,
        scope=SCOPE_LEADERBOARD,
        game_type_code="dominos",
        period=LeaderboardPeriod.all_time(),
    )

    assert context["schema_version"] == SCHEMA_VERSION
    assert context["scope"] == SCOPE_LEADERBOARD
    assert context["group"]["name"] == group.name
    assert context["rankings"]
    assert context["summary"]["player_count_ranked"] >= 1


@pytest.mark.django_db
def test_build_hall_of_fame_insight_context(client, user, group):
    client.force_login(user)
    client.post(reverse("games:create"), _load_roster_post(group))
    client.post(reverse("games:create"), _save_game_post(group))

    context = build_group_insight_context(
        group,
        scope=SCOPE_HALL_OF_FAME,
        granularity="year",
    )

    assert context["scope"] == SCOPE_HALL_OF_FAME
    assert context["period_leaders"]


@pytest.mark.django_db
@override_settings(
    INSIGHTS_ENABLED=True,
    OPENAI_API_KEY="test-openai",
    GOOGLE_AI_API_KEY="test-google",
)
@patch("leaderlodge.insights.views.generate_group_insight")
def test_group_insight_leaderboard_returns_markdown(mock_generate, client, user, group):
    mock_generate.return_value = _mock_group_insight_result()
    client.force_login(user)
    client.post(reverse("games:create"), _load_roster_post(group))
    client.post(reverse("games:create"), _save_game_post(group))

    response = client.post(
        reverse("insights:group"),
        data=json.dumps(
            {
                "group_id": str(group.pk),
                "scope": SCOPE_LEADERBOARD,
                "game_type_code": "dominos",
                "preset": "overview",
                "model": "flash-lite",
            }
        ),
        content_type="application/json",
    )

    assert response.status_code == 200
    payload = response.json()
    assert "Pat leads the board." in payload["markdown"]
    mock_generate.assert_called_once()


@pytest.mark.django_db
@override_settings(
    INSIGHTS_ENABLED=True,
    OPENAI_API_KEY="test-openai",
    GOOGLE_AI_API_KEY="test-google",
)
@patch("leaderlodge.insights.views.generate_group_insight")
def test_group_insight_hall_of_fame_meta_uses_period_count(
    mock_generate, client, user, group
):
    mock_generate.return_value = _mock_group_insight_result()
    client.force_login(user)
    client.post(reverse("games:create"), _load_roster_post(group))
    client.post(reverse("games:create"), _save_game_post(group))

    response = client.post(
        reverse("insights:group"),
        data=json.dumps(
            {
                "group_id": str(group.pk),
                "scope": SCOPE_HALL_OF_FAME,
                "granularity": "year",
                "preset": "overview",
                "model": "flash-lite",
            }
        ),
        content_type="application/json",
    )

    assert response.status_code == 200
    meta = response.json()["meta"]
    assert meta["scope"] == SCOPE_HALL_OF_FAME
    assert meta["period_count"] >= 1
    assert meta["granularity_label"] == "Years"
    assert "games_in_period" not in meta


