import pytest
from django.test import override_settings
from django.urls import reverse

from leaderlodge.core.brand import TAGLINE


@pytest.mark.django_db
def test_about_page_is_public(client):
    response = client.get(reverse("core:about"))
    content = response.content.decode()

    assert response.status_code == 200
    assert "About LeaderLodge" in content
    assert reverse("core:about_insights") in content


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
def test_site_footer_links_to_about_pages(client):
    content = client.get(reverse("core:about")).content.decode()

    assert "site-footer" in content
    assert reverse("core:about") in content
    assert reverse("core:about_insights") in content
    assert 'href="https://pixelmonks.com"' in content
    assert ">Pixelmonks</a>" in content
    assert "LeaderLodge</span>" not in content


@pytest.mark.django_db
def test_account_menu_includes_about_for_guest(client):
    content = client.get(reverse("accounts:login")).content.decode()

    assert reverse("core:about") in content
    assert ">About</a>" in content


@pytest.mark.django_db
def test_account_menu_includes_about_for_signed_in_user(client, django_user_model):
    from leaderlodge.groups.services import create_group_with_owner

    user = django_user_model.objects.create_user(
        username="david",
        password="test-pass-123",
    )
    create_group_with_owner(user=user, name="Dom Club")
    client.force_login(user)
    content = client.get(reverse("core:dashboard")).content.decode()

    assert reverse("core:about") in content
    assert ">About</a>" in content
