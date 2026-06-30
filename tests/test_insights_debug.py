import json
from unittest.mock import patch

import pytest
from django.contrib.auth.models import User
from django.test import override_settings
from django.urls import reverse

from leaderlodge.groups.services import add_guest_player, create_group_with_owner
from leaderlodge.insights.context.player import build_player_insight_context
from leaderlodge.insights.service import AskResult, InsightResult
from leaderlodge.leaderboards.period import LeaderboardPeriod
from tests.test_games import _load_roster_post, _save_game_post


@pytest.fixture
def user(db):
    return User.objects.create_user(username="david", password="test-pass-123")


@pytest.fixture
def staff_user(db):
    return User.objects.create_user(
        username="staff",
        password="test-pass-123",
        is_staff=True,
    )


@pytest.fixture
def staff_group(staff_user):
    group = create_group_with_owner(user=staff_user, name="Dom Club")
    add_guest_player(group=group, display_name="Pat")
    return group


@pytest.fixture
def group(user):
    group = create_group_with_owner(user=user, name="Dom Club")
    add_guest_player(group=group, display_name="Pat")
    return group


def _mock_insight_result(**overrides):
    defaults = {
        "markdown": "## Strengths\n\nSolid play.",
        "html": "<h2>Strengths</h2><p>Solid play.</p>",
        "model_slug": "gpt-4o-mini",
        "provider": "openai",
        "prompt_version": 1,
        "context_schema_version": 1,
        "cached": False,
        "input_tokens": 10,
        "output_tokens": 5,
    }
    defaults.update(overrides)
    return InsightResult(**defaults)


def _mock_ask_result(**overrides):
    defaults = {
        "markdown": "## Answer\n\nPat leads.",
        "html": "<h2>Answer</h2><p>Pat leads.</p>",
        "model_slug": "gpt-4o-mini",
        "provider": "openai",
        "prompt_version": 6,
        "context_schema_version": 1,
        "cached": False,
        "input_tokens": 10,
        "output_tokens": 5,
        "tools_used": ("query_leaderboard",),
        "debug": {
            "mode": "ask",
            "messages": [{"role": "user", "content": "Who leads?"}],
        },
    }
    defaults.update(overrides)
    return AskResult(**defaults)


@pytest.mark.django_db
@override_settings(
    INSIGHTS_ENABLED=True,
    OPENAI_API_KEY="test-openai",
    GOOGLE_AI_API_KEY="test-google",
)
@patch("leaderlodge.insights.views.generate_player_insight")
def test_player_insight_can_include_debug(mock_generate, client, user, group):
    client.force_login(user)
    client.post(reverse("games:create"), _load_roster_post(group))
    client.post(reverse("games:create"), _save_game_post(group))
    player = group.players.order_by("pk").first()
    mock_generate.return_value = _mock_insight_result()

    response = client.post(
        reverse("insights:player"),
        data=json.dumps(
            {
                "group_id": str(group.pk),
                "player_id": str(player.pk),
                "game_type_code": "dominos",
                "preset": "strengths",
                "model": "gpt-4o-mini",
                "include_debug": True,
            }
        ),
        content_type="application/json",
    )

    assert response.status_code == 200
    payload = response.json()
    assert "debug" in payload
    assert payload["debug"]["mode"] == "player"
    assert "context" in payload["debug"]
    assert (
        payload["debug"]["context"]["player"]["display_label"] == player.display_label
    )
    assert "system_prompt" in payload["debug"]
    assert "user_message" in payload["debug"]


@pytest.mark.django_db
@override_settings(
    INSIGHTS_ENABLED=True,
    OPENAI_API_KEY="test-openai",
    GOOGLE_AI_API_KEY="test-google",
)
@patch("leaderlodge.insights.views.generate_player_insight")
def test_staff_player_insight_can_include_debug(
    mock_generate, client, staff_user, staff_group
):
    client.force_login(staff_user)
    client.post(reverse("games:create"), _load_roster_post(staff_group))
    client.post(reverse("games:create"), _save_game_post(staff_group))
    player = staff_group.players.order_by("pk").first()
    mock_generate.return_value = _mock_insight_result()

    response = client.post(
        reverse("insights:player"),
        data=json.dumps(
            {
                "group_id": str(staff_group.pk),
                "player_id": str(player.pk),
                "game_type_code": "dominos",
                "preset": "strengths",
                "model": "gpt-4o-mini",
                "include_debug": True,
            }
        ),
        content_type="application/json",
    )

    assert response.status_code == 200
    assert "debug" in response.json()


@pytest.mark.django_db
@override_settings(
    INSIGHTS_ENABLED=True,
    OPENAI_API_KEY="test-openai",
    GOOGLE_AI_API_KEY="test-google",
)
@patch("leaderlodge.insights.views.generate_ask_response")
def test_staff_ask_query_returns_tool_debug(
    mock_generate, client, staff_user, staff_group
):
    client.force_login(staff_user)
    client.post(reverse("games:create"), _load_roster_post(staff_group))
    client.post(reverse("games:create"), _save_game_post(staff_group))
    mock_generate.return_value = _mock_ask_result()

    response = client.post(
        reverse("insights:ask_query"),
        data=json.dumps(
            {
                "group_id": str(staff_group.pk),
                "game_type_code": "dominos",
                "question": "Who leads?",
                "model": "gpt-4o-mini",
                "include_debug": True,
            }
        ),
        content_type="application/json",
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["debug"]["mode"] == "ask"
    assert payload["debug"]["messages"]
    mock_generate.assert_called_once()
    assert mock_generate.call_args.kwargs["collect_debug"] is True
    assert mock_generate.call_args.kwargs["skip_cache"] is True


@pytest.mark.django_db
@override_settings(
    INSIGHTS_ENABLED=True,
    OPENAI_API_KEY="test-openai",
    GOOGLE_AI_API_KEY="test-google",
)
def test_ask_page_shows_debug_toggle(client, user, group):
    client.force_login(user)
    client.post(reverse("games:create"), _load_roster_post(group))
    client.post(reverse("games:create"), _save_game_post(group))

    content = client.get(
        reverse("insights:ask"),
        {"group": str(group.pk), "game_type_code": "dominos"},
    ).content.decode()

    assert "Debug: Show data sent to AI" in content
    assert "insights_debug.js" in content
    assert 'id="ask-lodge-debug-toggle"' in content


@pytest.mark.django_db
@override_settings(
    INSIGHTS_ENABLED=True,
    OPENAI_API_KEY="test-openai",
    GOOGLE_AI_API_KEY="test-google",
)
def test_staff_ask_page_shows_debug_toggle(client, staff_user, staff_group):
    client.force_login(staff_user)
    client.post(reverse("games:create"), _load_roster_post(staff_group))
    client.post(reverse("games:create"), _save_game_post(staff_group))

    content = client.get(
        reverse("insights:ask"),
        {"group": str(staff_group.pk), "game_type_code": "dominos"},
    ).content.decode()

    assert "Debug: Show data sent to AI" in content
    assert "insights_debug.js" in content
    assert 'id="ask-lodge-debug-toggle"' in content


@pytest.mark.django_db
def test_build_player_insight_context_has_placement_data(client, user, group):
    client.force_login(user)
    client.post(reverse("games:create"), _load_roster_post(group))
    client.post(reverse("games:create"), _save_game_post(group))

    player = group.players.order_by("pk").first()
    context = build_player_insight_context(
        group,
        player,
        game_type_code="dominos",
        period=LeaderboardPeriod.all_time(),
    )

    assert context["placements"]
