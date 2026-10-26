import base64
from unittest.mock import MagicMock, patch

import pytest
from django.test import override_settings
from google.genai import types

from leaderlodge.insights.providers.base import InsightProviderError
from leaderlodge.insights.providers.google import (
    complete_google,
    complete_google_messages,
)
from leaderlodge.insights.registry import FLASH_LITE_API_MODEL, GEMINI_FLASH_API_MODEL


def _mock_google_response(*, text: str, candidates=None, usage_metadata=None):
    mock_response = MagicMock()
    mock_response.text = text
    if candidates is None:
        mock_part = MagicMock()
        mock_part.text = text
        mock_part.function_call = None
        mock_candidate = MagicMock()
        mock_candidate.content.parts = [mock_part]
        mock_candidate.finish_reason = None
        candidates = [mock_candidate]
    mock_response.candidates = candidates
    mock_response.usage_metadata = usage_metadata or MagicMock(
        prompt_token_count=100,
        candidates_token_count=40,
        thoughts_token_count=0,
    )
    return mock_response


@pytest.mark.django_db
@override_settings(GOOGLE_AI_API_KEY="test-google")
@patch("leaderlodge.insights.providers.google.genai.Client")
def test_complete_google_uses_minimal_thinking(mock_client_cls):
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    mock_client.models.generate_content.return_value = _mock_google_response(
        text="Full insight text."
    )

    result = complete_google(
        model_api_name=GEMINI_FLASH_API_MODEL,
        system="system",
        user="user",
        max_output_tokens=800,
        temperature=0.4,
    )

    assert result.text == "Full insight text."
    config = mock_client.models.generate_content.call_args.kwargs["config"]
    assert config.thinking_config.thinking_level == types.ThinkingLevel.MINIMAL
    assert config.thinking_config.thinking_budget is None


@pytest.mark.django_db
@override_settings(GOOGLE_AI_API_KEY="test-google")
@patch("leaderlodge.insights.providers.google.genai.Client")
def test_complete_google_flash_lite_503_uses_friendly_message(mock_client_cls):
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    mock_client.models.generate_content.side_effect = Exception(
        "503 UNAVAILABLE. This model is currently experiencing high demand."
    )

    with pytest.raises(
        InsightProviderError,
        match="Gemini Flash-Lite is busy. Try another model or try again later.",
    ):
        complete_google(
            model_api_name=FLASH_LITE_API_MODEL,
            system="system",
            user="user",
            max_output_tokens=800,
            temperature=0.4,
        )


@pytest.mark.django_db
@override_settings(GOOGLE_AI_API_KEY="test-google")
@patch("leaderlodge.insights.providers.google.genai.Client")
def test_complete_google_flash_503_keeps_provider_message(mock_client_cls):
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    mock_client.models.generate_content.side_effect = Exception(
        "503 UNAVAILABLE. This model is currently experiencing high demand."
    )

    with pytest.raises(InsightProviderError, match="503 UNAVAILABLE"):
        complete_google(
            model_api_name=GEMINI_FLASH_API_MODEL,
            system="system",
            user="user",
            max_output_tokens=800,
            temperature=0.4,
        )


@pytest.mark.django_db
@override_settings(GOOGLE_AI_API_KEY="test-google")
@patch("leaderlodge.insights.providers.google.genai.Client")
def test_complete_google_raises_when_thinking_eats_budget(mock_client_cls):
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    mock_candidate = MagicMock()
    mock_candidate.finish_reason = "MAX_TOKENS"
    mock_candidate.content = None
    mock_client.models.generate_content.return_value = _mock_google_response(
        text="That's an impressive",
        candidates=[mock_candidate],
        usage_metadata=MagicMock(
            prompt_token_count=100,
            candidates_token_count=5,
            thoughts_token_count=795,
        ),
    )

    with pytest.raises(InsightProviderError, match="truncated"):
        complete_google(
            model_api_name=GEMINI_FLASH_API_MODEL,
            system="system",
            user="user",
            max_output_tokens=800,
            temperature=0.4,
        )


@pytest.mark.django_db
@override_settings(GOOGLE_AI_API_KEY="test-google")
@patch("leaderlodge.insights.providers.google.genai.Client")
def test_complete_google_messages_echoes_thought_signature(mock_client_cls):
    signature = b"sig-bytes"
    function_call = MagicMock()
    function_call.name = "query_leaderboard"
    function_call.id = "call_abc"
    function_call.args = {"all_time": True}
    call_part = MagicMock()
    call_part.thought = False
    call_part.text = None
    call_part.function_call = function_call
    call_part.thought_signature = signature
    thought_part = MagicMock()
    thought_part.thought = True
    thought_part.text = "internal reasoning"
    thought_part.function_call = None
    candidate = MagicMock()
    candidate.content.parts = [thought_part, call_part]
    candidate.finish_reason = None
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    mock_client.models.generate_content.return_value = _mock_google_response(
        text="",
        candidates=[candidate],
    )

    first = complete_google_messages(
        model_api_name=GEMINI_FLASH_API_MODEL,
        messages=[{"role": "user", "content": "who leads"}],
        system="system",
        tools=[{"function": {"name": "query_leaderboard", "parameters": {}}}],
        max_output_tokens=800,
        temperature=0.3,
    )

    assert first.text == ""
    assert first.tool_calls[0].id == "call_abc"
    assert first.tool_calls[0].thought_signature == base64.b64encode(signature).decode(
        "ascii"
    )

    complete_google_messages(
        model_api_name=GEMINI_FLASH_API_MODEL,
        messages=[
            {"role": "user", "content": "who leads"},
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "call_abc",
                        "function": {
                            "name": "query_leaderboard",
                            "arguments": '{"all_time": true}',
                        },
                        "thought_signature": first.tool_calls[0].thought_signature,
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "call_abc",
                "name": "query_leaderboard",
                "content": "{}",
            },
        ],
        system="system",
        tools=[{"function": {"name": "query_leaderboard", "parameters": {}}}],
        max_output_tokens=800,
        temperature=0.3,
    )

    contents = mock_client.models.generate_content.call_args.kwargs["contents"]
    assert contents[1].parts[0].thought_signature == signature
    assert contents[2].parts[0].function_response.id == "call_abc"
