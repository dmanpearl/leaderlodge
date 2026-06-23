import pytest
from django.contrib.auth.models import User
from django.urls import reverse


@pytest.fixture
def user(db):
    return User.objects.create_user(username="testuser", password="test-pass-123")


@pytest.mark.django_db
def test_csrf_token_endpoint_returns_token(client):
    response = client.get(reverse("accounts:csrf_token"))
    assert response.status_code == 200
    data = response.json()
    assert data["csrfToken"]


@pytest.mark.django_db
def test_csrf_token_endpoint_works_for_logged_in_user(client, user):
    client.force_login(user)
    response = client.get(reverse("accounts:csrf_token"))
    assert response.status_code == 200
    assert response.json()["csrfToken"]
