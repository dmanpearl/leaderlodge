from unittest.mock import MagicMock, patch

import pytest
from django.test import override_settings

from leaderlodge.insights.providers.base import InsightProviderError
from leaderlodge.insights.providers.google import complete_google


@pytest.mark.django_db
@override_settings(GOOGLE_AI_API_KEY="test-google")
@patch("leaderlodge.insights.providers.google.genai.Client")
def test_complete_google_disables_thinking_budget(mock_client_cls):
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    mock_response = MagicMock()
    mock_response.text = "Full insight text."
    mock_response.candidates = []
    mock_response.usage_metadata = MagicMock(
        prompt_token_count=100,
        candidates_token_count=40,
        thoughts_token_count=0,
    )
    mock_client.models.generate_content.return_value = mock_response

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
def test_complete_google_raises_when_thinking_eats_budget(mock_client_cls):
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    mock_response = MagicMock()
    mock_response.text = "That's an impressive"
    mock_candidate = MagicMock()
    mock_candidate.finish_reason = "MAX_TOKENS"
    mock_response.candidates = [mock_candidate]
    mock_response.usage_metadata = MagicMock(
        prompt_token_count=100,
        candidates_token_count=5,
        thoughts_token_count=795,
    )
    mock_client.models.generate_content.return_value = mock_response

    with pytest.raises(InsightProviderError, match="truncated"):
        complete_google(
            model_api_name="gemini-2.5-flash",
            system="system",
            user="user",
            max_output_tokens=800,
            temperature=0.4,
        )
