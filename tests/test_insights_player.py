import json
from unittest.mock import patch

import pytest
from django.contrib.auth.models import User
from django.test import override_settings
from django.urls import reverse

from leaderlodge.groups.services import add_guest_player, create_group_with_owner
from leaderlodge.insights.context.player import (
    SCHEMA_VERSION,
    build_player_insight_context,
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
    return group


def _mock_insight_result(**overrides):
    defaults = {
        "markdown": "## Strengths\n\nPat plays solid dominos.",
        "html": "<h2>Strengths</h2><p>Pat plays solid dominos.</p>",
        "model_slug": "flash-lite",
        "provider": "google",
        "prompt_version": 1,
        "context_schema_version": SCHEMA_VERSION,
        "cached": False,
        "input_tokens": 100,
        "output_tokens": 50,
    }
    defaults.update(overrides)
    return InsightResult(**defaults)


@pytest.mark.django_db
def test_build_player_insight_context(client, user, group):
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

    assert context["schema_version"] == SCHEMA_VERSION
    assert context["player"]["display_label"] == player.display_label
    assert context["game_type"]["code"] == "dominos"
    assert context["ranking"]["games_played"] >= 1
    assert "placements" in context
    assert "group_comparison" in context


@pytest.mark.django_db
@override_settings(INSIGHTS_ENABLED=False)
def test_player_insight_disabled(client, user, group):
    client.force_login(user)
    client.post(reverse("games:create"), _load_roster_post(group))
    client.post(reverse("games:create"), _save_game_post(group))
    player = group.players.order_by("pk").first()

    response = client.post(
        reverse("insights:player"),
        data=json.dumps(
            {
                "group_id": str(group.pk),
                "player_id": str(player.pk),
                "game_type_code": "dominos",
                "preset": "strengths",
                "model": "flash-lite",
            }
        ),
        content_type="application/json",
    )
    assert response.status_code == 404


@pytest.mark.django_db
@override_settings(
    INSIGHTS_ENABLED=True,
    OPENAI_API_KEY="test-openai",
    GOOGLE_AI_API_KEY="test-google",
)
@patch("leaderlodge.insights.views.generate_player_insight")
def test_player_insight_returns_markdown(mock_generate, client, user, group):
    mock_generate.return_value = _mock_insight_result()
    client.force_login(user)
    client.post(reverse("games:create"), _load_roster_post(group))
    client.post(reverse("games:create"), _save_game_post(group))
    player = group.players.order_by("pk").first()

    response = client.post(
        reverse("insights:player"),
        data=json.dumps(
            {
                "group_id": str(group.pk),
                "player_id": str(player.pk),
                "game_type_code": "dominos",
                "preset": "strengths",
                "model": "flash-lite",
            }
        ),
        content_type="application/json",
    )

    assert response.status_code == 200
    payload = response.json()
    assert "Pat plays solid dominos." in payload["markdown"]
    assert payload["meta"]["model"] == "flash-lite"
    mock_generate.assert_called_once()


@pytest.mark.django_db
@override_settings(
    INSIGHTS_ENABLED=True,
    OPENAI_API_KEY="test-openai",
    GOOGLE_AI_API_KEY="test-google",
)
def test_rank_detail_shows_insights_button(client, user, group):
    client.force_login(user)
    client.post(reverse("games:create"), _load_roster_post(group))
    client.post(reverse("games:create"), _save_game_post(group))
    player = group.players.order_by("pk").first()

    response = client.get(
        reverse("leaderboards:detail"),
        {
            "group": str(group.pk),
            "game_type_code": "dominos",
            "player": str(player.pk),
        },
    )
    content = response.content.decode()
    assert response.status_code == 200
    assert 'id="player-insights-panel"' in content
    assert "btn-insights" in content
    assert "Insights" in content
    assert "player_insights.js" in content


@pytest.mark.django_db
@override_settings(
    INSIGHTS_ENABLED=False,
    OPENAI_API_KEY="test-openai",
    GOOGLE_AI_API_KEY="",
)
def test_rank_detail_shows_insights_when_keys_present(client, user, group):
    client.force_login(user)
    client.post(reverse("games:create"), _load_roster_post(group))
    client.post(reverse("games:create"), _save_game_post(group))
    player = group.players.order_by("pk").first()

    content = client.get(
        reverse("leaderboards:detail"),
        {
            "group": str(group.pk),
            "game_type_code": "dominos",
            "player": str(player.pk),
        },
    ).content.decode()

    assert 'id="player-insights-panel"' in content


@pytest.mark.django_db
@override_settings(INSIGHTS_ENABLED=False, OPENAI_API_KEY="", GOOGLE_AI_API_KEY="")
def test_rank_detail_hides_insights_button(client, user, group):
    client.force_login(user)
    client.post(reverse("games:create"), _load_roster_post(group))
    client.post(reverse("games:create"), _save_game_post(group))
    player = group.players.order_by("pk").first()

    content = client.get(
        reverse("leaderboards:detail"),
        {
            "group": str(group.pk),
            "game_type_code": "dominos",
            "player": str(player.pk),
        },
    ).content.decode()

    assert 'id="player-insights-panel"' not in content
