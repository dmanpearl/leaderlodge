import pytest
from django.test import override_settings
from django.urls import reverse

from leaderlodge.core.brand import TAGLINE
from leaderlodge.feedback.prompts import GUEST_FEEDBACK_AUTH_MESSAGE


@pytest.mark.django_db
def test_about_insights_page_is_public(client):
    response = client.get(reverse("core:about_insights"))
    content = response.content.decode()

    assert response.status_code == 200
    assert "How AI works in LeaderLodge" in content
    assert TAGLINE in content
    assert reverse("core:about") in content


@pytest.mark.django_db
@override_settings(
    INSIGHTS_ENABLED=True,
    OPENAI_API_KEY="test-openai",
    GOOGLE_AI_API_KEY="test-google",
)
def test_about_insights_links_to_ask_when_enabled(client):
    content = client.get(reverse("core:about_insights")).content.decode()

    assert reverse("insights:ask") in content
    assert reverse("insights:ask_examples") in content
    assert "btn-insights" in content
    assert "Examples" in content
    assert "About LeaderLodge" not in content


@pytest.mark.django_db
def test_about_page_guest_feedback_uses_auth_dialog(client):
    content = client.get(reverse("core:about")).content.decode()

    assert "guest-auth-dialog" in content
    assert "data-guest-auth-trigger" in content
    assert "data-guest-auth-next" in content
    assert GUEST_FEEDBACK_AUTH_MESSAGE in content
    assert f'href="{reverse("feedback:create")}"' not in content


@pytest.mark.django_db
def test_about_page_authenticated_feedback_links_directly(client, django_user_model):
    user = django_user_model.objects.create_user(
        username="david",
        password="test-pass-123",
    )
    client.force_login(user)
    content = client.get(reverse("core:about")).content.decode()

    assert reverse("feedback:create") in content
    assert "data-guest-auth-trigger" not in content
    assert "guest-auth-dialog" not in content
