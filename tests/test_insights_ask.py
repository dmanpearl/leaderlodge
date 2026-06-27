import json
from unittest.mock import patch

import pytest
from django.contrib.auth.models import User
from django.test import override_settings
from django.urls import reverse

from leaderlodge.groups.services import add_guest_player, create_group_with_owner
from leaderlodge.insights.service import AskResult
from tests.test_games import _load_roster_post, _save_game_post


@pytest.fixture
def user(db):
    return User.objects.create_user(username="david", password="test-pass-123")


@pytest.fixture
def group(user):
    group = create_group_with_owner(user=user, name="Dom Club")
    add_guest_player(group=group, display_name="Pat")
    return group


def _mock_ask_result(**overrides):
    defaults = {
        "markdown": "## Answer\n\nPat is improving most.",
        "html": "<h2>Answer</h2><p>Pat is improving most.</p>",
        "model_slug": "flash-lite",
        "provider": "google",
        "prompt_version": 6,
        "context_schema_version": 1,
        "cached": False,
        "input_tokens": 120,
        "output_tokens": 60,
        "tools_used": ("query_rank_trends",),
    }
    defaults.update(overrides)
    return AskResult(**defaults)


@pytest.mark.django_db
@override_settings(
    INSIGHTS_ENABLED=True,
    OPENAI_API_KEY="test-openai",
    GOOGLE_AI_API_KEY="test-google",
)
def test_ask_page_renders(client, user, group):
    client.force_login(user)
    client.post(reverse("games:create"), _load_roster_post(group))
    client.post(reverse("games:create"), _save_game_post(group))

    response = client.get(
        reverse("insights:ask"),
        {"group": str(group.pk), "game_type_code": "dominos"},
    )
    content = response.content.decode()

    assert response.status_code == 200
    assert "Ask the Lodge" in content
    assert 'id="ask-question"' in content
    assert "ask_lodge.js" in content


@pytest.mark.django_db
@override_settings(
    INSIGHTS_ENABLED=False,
    OPENAI_API_KEY="",
    GOOGLE_AI_API_KEY="",
)
def test_ask_page_hidden_when_insights_disabled(client, user, group):
    client.force_login(user)
    response = client.get(reverse("insights:ask"))
    assert response.status_code == 404


@pytest.mark.django_db
@override_settings(
    INSIGHTS_ENABLED=True,
    OPENAI_API_KEY="test-openai",
    GOOGLE_AI_API_KEY="test-google",
)
@patch("leaderlodge.insights.views.generate_ask_response")
def test_ask_query_returns_markdown(mock_generate, client, user, group):
    client.force_login(user)
    client.post(reverse("games:create"), _load_roster_post(group))
    client.post(reverse("games:create"), _save_game_post(group))
    mock_generate.return_value = _mock_ask_result()

    response = client.post(
        reverse("insights:ask_query"),
        data=json.dumps(
            {
                "group_id": str(group.pk),
                "game_type_code": "dominos",
                "question": "Which player is improving most in the past quarter?",
                "model": "flash-lite",
            }
        ),
        content_type="application/json",
    )
    data = response.json()

    assert response.status_code == 200
    assert "Pat is improving most." in data["markdown"]
    assert data["meta"]["tools_used"] == ["query_rank_trends"]
    mock_generate.assert_called_once()
