import pytest
from django.contrib.auth.models import User
from django.urls import reverse


@pytest.fixture
def user(db):
    return User.objects.create_user(username="testuser", password="test-pass-123")


@pytest.mark.django_db
def test_csrf_token_endpoint_returns_token_and_sets_cookie(client):
    response = client.get(reverse("accounts:csrf_token"))
    assert response.status_code == 200
    data = response.json()
    assert data["csrfToken"]
    assert response.cookies.get("csrftoken")


@pytest.mark.django_db
def test_csrf_token_endpoint_works_for_logged_in_user(client, user):
    client.force_login(user)
    response = client.get(reverse("accounts:csrf_token"))
    assert response.status_code == 200
    assert response.json()["csrfToken"]
    assert response.cookies.get("csrftoken") or client.cookies.get("csrftoken")


@pytest.mark.django_db
def test_csrf_refresh_script_is_on_base_pages(client, user):
    client.force_login(user)
    content = client.get(reverse("core:dashboard")).content.decode()
    assert "csrf_refresh.js" in content
    assert 'data-csrf-refresh-url="' in content
    assert reverse("accounts:csrf_token") in content
