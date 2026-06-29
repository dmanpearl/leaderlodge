from unittest.mock import MagicMock, patch

import pytest
from django.test import override_settings

from leaderlodge.insights.providers.base import InsightProviderError
from leaderlodge.insights.providers.google import complete_google


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
def test_complete_google_disables_thinking_budget(mock_client_cls):
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    mock_client.models.generate_content.return_value = _mock_google_response(
        text="Full insight text."
    )

    result = complete_google(
        model_api_name="gemini-2.5-flash",
        system="system",
        user="user",
        max_output_tokens=800,
        temperature=0.4,
    )

    assert result.text == "Full insight text."
    config = mock_client.models.generate_content.call_args.kwargs["config"]
    assert config.thinking_config.thinking_budget == 0


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
            model_api_name="gemini-2.5-flash-lite",
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
            model_api_name="gemini-2.5-flash",
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
            model_api_name="gemini-2.5-flash",
            system="system",
            user="user",
            max_output_tokens=800,
            temperature=0.4,
        )
