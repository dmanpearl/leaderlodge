import json
from unittest.mock import patch

import pytest
from django.contrib.auth.models import User
from django.test import override_settings
from django.urls import reverse

from leaderlodge.groups.services import add_guest_player, create_group_with_owner
from leaderlodge.insights.providers.base import InsightCompletion, ToolCall
from leaderlodge.insights.service import generate_ask_response
from leaderlodge.insights.tools.scope import AskScope
from leaderlodge.leaderboards.period import LeaderboardPeriod
from tests.test_games import _load_roster_post, _save_game_post


@pytest.fixture
def rivalry_group(db):
    nancy = User.objects.create_user(
        username="nmanpearl",
        password="test-pass-123",
        first_name="Nancy",
    )
    david = User.objects.create_user(
        username="dmanpearl",
        password="test-pass-123",
        first_name="David",
    )
    group = create_group_with_owner(user=nancy, name="Dom Club")
    david_player = add_guest_player(group=group, display_name="David Guest")
    david_player.linked_user = david
    david_player.save(update_fields=["linked_user"])
    return group, nancy


def _scope(group):
    return AskScope(
        group=group,
        period=LeaderboardPeriod.all_time(),
        default_game_type_code="dominos",
        available_game_type_codes=("dominos",),
    )


@pytest.mark.django_db
@patch("leaderlodge.insights.service.complete_with_tools")
def test_generate_ask_response_handles_two_player_queries(mock_complete, rivalry_group):
    group, _user = rivalry_group
    call_count = {"n": 0}

    def fake_complete(**kwargs):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return InsightCompletion(
                text="",
                tool_calls=(
                    ToolCall(
                        id="1",
                        name="query_player_detail",
                        arguments={
                            "player_query": "Nancy",
                            "game_type_code": "dominos",
                        },
                    ),
                    ToolCall(
                        id="2",
                        name="query_player_detail",
                        arguments={
                            "player_query": "David",
                            "game_type_code": "dominos",
                        },
                    ),
                ),
                input_tokens=10,
                output_tokens=5,
                model_api_name="gpt-4o-mini",
                provider="openai",
            )
        return InsightCompletion(
            text="## Rivalry\n\nNancy leads David in dominos.",
            tool_calls=(),
            input_tokens=10,
            output_tokens=20,
            model_api_name="gpt-4o-mini",
            provider="openai",
        )

    mock_complete.side_effect = fake_complete

    result = generate_ask_response(
        scope=_scope(group),
        question="How do Nancy and David stack up against each other in dominos?",
        model_slug="gpt-4o-mini",
    )

    assert "Nancy leads David" in result.markdown
    assert call_count["n"] == 2


@pytest.mark.django_db
@override_settings(
    INSIGHTS_ENABLED=True,
    OPENAI_API_KEY="test-openai",
    GOOGLE_AI_API_KEY="test-google",
)
@patch("leaderlodge.insights.views.generate_ask_response")
def test_ask_query_returns_json_on_success(mock_generate, client, rivalry_group):
    group, user = rivalry_group
    client.force_login(user)
    client.post(reverse("games:create"), _load_roster_post(group))
    client.post(reverse("games:create"), _save_game_post(group))

    from leaderlodge.insights.service import AskResult

    mock_generate.return_value = AskResult(
        markdown="## Answer\n\nNancy leads.",
        html="<h2>Answer</h2><p>Nancy leads.</p>",
        model_slug="flash-lite",
        provider="google",
        prompt_version=7,
        context_schema_version=1,
        cached=False,
        input_tokens=1,
        output_tokens=1,
        tools_used=("query_player_detail",),
    )

    response = client.post(
        reverse("insights:ask_query"),
        data=json.dumps(
            {
                "group_id": str(group.pk),
                "game_type_code": "dominos",
                "question": "How do Nancy and David stack up against each other in dominos?",
                "model": "flash-lite",
            }
        ),
        content_type="application/json",
    )

    assert response.status_code == 200
    assert response["Content-Type"] == "application/json"
    assert "Nancy leads." in response.json()["markdown"]


@pytest.mark.django_db
@override_settings(
    INSIGHTS_ENABLED=True,
    OPENAI_API_KEY="test-openai",
    GOOGLE_AI_API_KEY="test-google",
)
@patch("leaderlodge.insights.service.complete_with_tools")
def test_ask_query_view_with_tool_loop(mock_complete, client, rivalry_group):
    group, user = rivalry_group
    client.force_login(user)
    client.post(reverse("games:create"), _load_roster_post(group))
    client.post(reverse("games:create"), _save_game_post(group))

    call_count = {"n": 0}

    def fake_complete(**kwargs):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return InsightCompletion(
                text="",
                tool_calls=(
                    ToolCall(
                        id="1",
                        name="query_player_detail",
                        arguments={
                            "player_query": "Nancy",
                            "game_type_code": "dominos",
                        },
                    ),
                    ToolCall(
                        id="2",
                        name="query_player_detail",
                        arguments={
                            "player_query": "David",
                            "game_type_code": "dominos",
                        },
                    ),
                ),
                input_tokens=10,
                output_tokens=5,
                model_api_name="gemini-2.5-flash-lite",
                provider="google",
            )
        return InsightCompletion(
            text="## Rivalry\n\nNancy leads David in dominos.",
            tool_calls=(),
            input_tokens=10,
            output_tokens=20,
            model_api_name="gemini-2.5-flash-lite",
            provider="google",
        )

    mock_complete.side_effect = fake_complete

    response = client.post(
        reverse("insights:ask_query"),
        data=json.dumps(
            {
                "group_id": str(group.pk),
                "game_type_code": "dominos",
                "question": "How do Nancy and David stack up against each other in dominos?",
                "model": "flash-lite",
            }
        ),
        content_type="application/json",
    )

    assert response.status_code == 200, response.content.decode()
    assert "Nancy leads David" in response.json()["markdown"]
