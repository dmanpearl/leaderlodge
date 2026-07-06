import json
import pytest
from django.urls import reverse
from unittest.mock import patch

from leaderlodge.groups.services import add_guest_player, create_group_with_owner
from leaderlodge.insights.insight_log import (
    InsightLogDraft,
    question_for_log,
    summarize_insight_context,
)
from leaderlodge.insights.models import InsightLog
from leaderlodge.insights.prompts import PRESET_STRENGTHS
from leaderlodge.insights.service import AskResult, InsightResult
from tests.test_games import _load_roster_post, _save_game_post


@pytest.fixture
def user(db):
    from django.contrib.auth.models import User

    return User.objects.create_user(username="david", password="test-pass-123")


@pytest.fixture
def group(user):
    group = create_group_with_owner(user=user, name="Dom Club")
    add_guest_player(group=group, display_name="Pat")
    return group


def test_question_for_log_stores_rendered_preset_text():
    question = question_for_log(
        source=InsightLog.Source.PLAYER,
        preset=PRESET_STRENGTHS,
    )
    assert question == "Summarize this player's strengths based on the JSON."


def test_summarize_player_context():
    summary = summarize_insight_context(
        InsightLog.Source.PLAYER,
        {
            "player": {"display_label": "Amelia"},
            "period": {"label": "2026"},
            "ranking": {"rank": 2, "games_played": 12},
            "data_quality": {"sparse": False},
        },
    )
    assert summary["player_label"] == "Amelia"
    assert summary["rank"] == 2


@pytest.mark.django_db
def test_insight_log_draft_save_success(user, group, rf):
    player = group.players.filter(linked_user__isnull=False).first()
    request = rf.post("/insights/player/")
    request.user = user
    draft = InsightLogDraft(
        request=request,
        payload={"refresh": True},
        source=InsightLog.Source.PLAYER,
        preset=PRESET_STRENGTHS,
        group=group,
        player=player,
        game_type_code="dominos",
        model_slug="gpt-4o-mini",
        insight_context={
            "player": {"display_label": player.display_label},
            "period": {"label": ""},
            "ranking": {"rank": 1, "games_played": 5},
            "data_quality": {"sparse": True},
        },
    )
    result = InsightResult(
        markdown="Amelia leads.",
        html="<p>Amelia leads.</p>",
        model_slug="gpt-4o-mini",
        provider="openai",
        prompt_version=29,
        context_schema_version=1,
        cached=False,
        input_tokens=100,
        output_tokens=50,
    )

    log = draft.save(
        http_status=200,
        answer_markdown=result.markdown,
        result=result,
    )

    assert log.is_failure is False
    assert log.is_regenerate is True
    assert log.question.startswith("Summarize this player's strengths")
    assert log.answer_markdown == "Amelia leads."
    assert log.context_summary["sparse"] is True


@patch("leaderlodge.insights.views.generate_ask_response")
@pytest.mark.django_db
def test_ask_query_returns_log_id(mock_generate, client, user, group):
    from django.test import override_settings

    client.force_login(user)
    client.post(reverse("games:create"), _load_roster_post(group))
    client.post(reverse("games:create"), _save_game_post(group))
    mock_generate.return_value = AskResult(
        markdown="Pat leads.",
        html="<p>Pat leads.</p>",
        model_slug="flash-lite",
        provider="google",
        prompt_version=29,
        context_schema_version=1,
        cached=False,
        input_tokens=10,
        output_tokens=5,
        tools_used=("query_leaderboard",),
        coverage=None,
    )

    with override_settings(
        INSIGHTS_ENABLED=True,
        OPENAI_API_KEY="test-openai",
        GOOGLE_AI_API_KEY="test-google",
    ):
        response = client.post(
            reverse("insights:ask_query"),
            data=json.dumps(
                {
                    "group_id": str(group.pk),
                    "game_type_code": "dominos",
                    "question": "Who leads?",
                    "model": "flash-lite",
                }
            ),
            content_type="application/json",
        )

    assert response.status_code == 200
    data = response.json()
    assert data["log_id"]
    log = InsightLog.objects.get(pk=data["log_id"])
    assert log.source == InsightLog.Source.ASK
    assert log.question == "Who leads?"
    assert log.is_failure is False


@patch("leaderlodge.insights.views.generate_ask_response")
@pytest.mark.django_db
def test_ask_query_regenerate_links_parent_log(mock_generate, client, user, group):
    from django.test import override_settings

    client.force_login(user)
    client.post(reverse("games:create"), _load_roster_post(group))
    client.post(reverse("games:create"), _save_game_post(group))
    mock_generate.return_value = AskResult(
        markdown="Answer",
        html="<p>Answer</p>",
        model_slug="flash-lite",
        provider="google",
        prompt_version=29,
        context_schema_version=1,
        cached=False,
        input_tokens=10,
        output_tokens=5,
    )

    with override_settings(
        INSIGHTS_ENABLED=True,
        OPENAI_API_KEY="test-openai",
        GOOGLE_AI_API_KEY="test-google",
    ):
        first = client.post(
            reverse("insights:ask_query"),
            data=json.dumps(
                {
                    "group_id": str(group.pk),
                    "game_type_code": "dominos",
                    "question": "Who leads?",
                }
            ),
            content_type="application/json",
        )
        parent_id = first.json()["log_id"]
        second = client.post(
            reverse("insights:ask_query"),
            data=json.dumps(
                {
                    "group_id": str(group.pk),
                    "game_type_code": "dominos",
                    "question": "Who leads?",
                    "refresh": True,
                    "regenerate_of_id": parent_id,
                }
            ),
            content_type="application/json",
        )

    child = InsightLog.objects.get(pk=second.json()["log_id"])
    assert child.is_regenerate is True
    assert child.regenerate_of_id == int(parent_id)


@pytest.mark.django_db
def test_ask_query_logs_validation_failure(client, user, group):
    from django.test import override_settings

    client.force_login(user)
    with override_settings(
        INSIGHTS_ENABLED=True,
        OPENAI_API_KEY="test-openai",
        GOOGLE_AI_API_KEY="test-google",
    ):
        response = client.post(
            reverse("insights:ask_query"),
            data=json.dumps({"group_id": str(group.pk), "question": ""}),
            content_type="application/json",
        )

    assert response.status_code == 400
    log = InsightLog.objects.get(pk=response.json()["log_id"])
    assert log.is_failure is True
    assert log.error_message == "Missing required fields."
