import json
from unittest.mock import patch

import pytest
from django.contrib.auth.models import User
from django.test import override_settings
from django.urls import reverse

from leaderlodge.games.models import Game
from leaderlodge.groups.services import add_guest_player, create_group_with_owner
from leaderlodge.insights.context.matchup import SCHEMA_VERSION, build_matchup_insight_context
from leaderlodge.insights.service import InsightResult
from tests.test_games import _load_roster_post, _save_game_post


@pytest.fixture
def user(db):
    return User.objects.create_user(username="david", password="test-pass-123")


@pytest.fixture
def group(user):
    group = create_group_with_owner(user=user, name="Dom Club")
    add_guest_player(group=group, display_name="Pat")
    add_guest_player(group=group, display_name="Sam")
    return group


def _mock_matchup_insight_result(**overrides):
    defaults = {
        "markdown": "## Dynamics\n\nPat has the edge head to head.",
        "html": "<h2>Dynamics</h2><p>Pat has the edge head to head.</p>",
        "model_slug": "flash-lite",
        "provider": "google",
        "prompt_version": 4,
        "context_schema_version": SCHEMA_VERSION,
        "cached": False,
        "input_tokens": 200,
        "output_tokens": 60,
    }
    defaults.update(overrides)
    return InsightResult(**defaults)


@pytest.mark.django_db
def test_build_matchup_insight_context(client, user, group):
    client.force_login(user)
    client.post(reverse("games:create"), _load_roster_post(group))
    players = list(group.players.order_by("pk")[:2])
    client.post(
        reverse("games:create"),
        _save_game_post(group, players_played=players, scores={players[0].pk: 30, players[1].pk: 20}),
    )
    game = Game.objects.get(group=group)

    context = build_matchup_insight_context(game)

    assert context["schema_version"] == SCHEMA_VERSION
    assert context["scope"] == "matchup"
    assert len(context["player_summaries"]) == 2
    assert context["matchup_table"]
    assert context["game"]["id"] == game.pk


@pytest.mark.django_db
@override_settings(
    INSIGHTS_ENABLED=True,
    OPENAI_API_KEY="test-openai",
    GOOGLE_AI_API_KEY="test-google",
)
@patch("leaderlodge.insights.views.generate_matchup_insight")
def test_matchup_insight_returns_markdown(mock_generate, client, user, group):
    mock_generate.return_value = _mock_matchup_insight_result()
    client.force_login(user)
    client.post(reverse("games:create"), _load_roster_post(group))
    players = list(group.players.order_by("pk")[:2])
    client.post(
        reverse("games:create"),
        _save_game_post(group, players_played=players, scores={players[0].pk: 30, players[1].pk: 20}),
    )
    game = Game.objects.get(group=group)

    response = client.post(
        reverse("insights:matchup"),
        data=json.dumps(
            {
                "game_id": str(game.pk),
                "preset": "dynamics",
                "model": "flash-lite",
            }
        ),
        content_type="application/json",
    )

    assert response.status_code == 200
    assert "Pat has the edge head to head." in response.json()["markdown"]
    mock_generate.assert_called_once()


@pytest.mark.django_db
@override_settings(
    INSIGHTS_ENABLED=True,
    OPENAI_API_KEY="test-openai",
    GOOGLE_AI_API_KEY="test-google",
)
def test_matchup_view_shows_insights_button(client, user, group):
    client.force_login(user)
    client.post(reverse("games:create"), _load_roster_post(group))
    players = list(group.players.order_by("pk")[:2])
    client.post(
        reverse("games:create"),
        _save_game_post(group, players_played=players, scores={players[0].pk: 30, players[1].pk: 20}),
    )
    game = Game.objects.get(group=group)

    content = client.get(reverse("games:matchup"), {"game": game.pk}).content.decode()

    assert "btn-insights" in content
    assert 'id="matchup-insights-panel"' in content
    assert "matchup_insights.js" in content
