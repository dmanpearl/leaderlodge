import re

import pytest
from django.contrib.auth.models import User
from django.core import mail
from django.test import Client
from django.urls import reverse

from leaderlodge.accounts.models import UserProfile
from leaderlodge.accounts.registration import (
    unique_username_for_email,
    username_base_from_email,
)


@pytest.fixture
def user(db):
    return User.objects.create_user(username="david", password="test-pass-123")


@pytest.fixture
def client():
    return Client()


@pytest.mark.django_db
def test_username_base_from_email():
    assert username_base_from_email("David.Pearl@Example.com") == "david.pearl"


@pytest.mark.django_db
def test_unique_username_for_email_adds_suffix_on_collision():
    User.objects.create_user(username="david", password="x")
    assert unique_username_for_email("david@example.com") == "david2"


@pytest.mark.django_db
def test_signup_creates_user_profile_and_logs_in(client):
    response = client.post(
        reverse("accounts:signup"),
        {
            "email": "newplayer@example.com",
            "first_name": "New",
            "password1": "strong-pass-123",
            "password2": "strong-pass-123",
        },
    )

    assert response.status_code == 302
    assert response.url == reverse("core:dashboard")

    user = User.objects.get(email="newplayer@example.com")
    assert user.first_name == "New"
    assert user.username == "newplayer"
    assert UserProfile.objects.filter(user=user).exists()


@pytest.mark.django_db
def test_signup_rejects_duplicate_email(client, user):
    user.email = "david@example.com"
    user.save(update_fields=["email"])

    response = client.post(
        reverse("accounts:signup"),
        {
            "email": "David@Example.com",
            "password1": "strong-pass-123",
            "password2": "strong-pass-123",
        },
    )

    assert response.status_code == 200
    assert "already exists" in response.content.decode()


@pytest.mark.django_db
def test_login_accepts_email_or_username(client, user):
    user.email = "david@example.com"
    user.set_password("secret-pass")
    user.save(update_fields=["email", "password"])

    by_email = client.post(
        reverse("accounts:login"),
        {"username": "david@example.com", "password": "secret-pass"},
    )
    assert by_email.status_code == 302

    client.logout()

    by_username = client.post(
        reverse("accounts:login"),
        {"username": user.username, "password": "secret-pass"},
    )
    assert by_username.status_code == 302


@pytest.mark.django_db
def test_password_reset_sends_email(client, user):
    user.email = "david@example.com"
    user.save(update_fields=["email"])

    response = client.post(
        reverse("accounts:password_reset"),
        {"email": "david@example.com"},
    )

    assert response.status_code == 302
    assert len(mail.outbox) == 1
    assert "david@example.com" in mail.outbox[0].to
    assert "Reset your LeaderLodge password" in mail.outbox[0].subject


@pytest.mark.django_db
def test_password_reset_confirm_updates_password(client, user):
    user.email = "david@example.com"
    user.set_password("old-pass")
    user.save(update_fields=["email", "password"])

    client.post(
        reverse("accounts:password_reset"),
        {"email": "david@example.com"},
    )
    body = mail.outbox[0].body
    match = re.search(r"http://testserver(/accounts/reset/[^\s]+)", body)
    assert match is not None

    reset_url = match.group(1)
    token_step = client.get(reset_url)
    assert token_step.status_code == 302
    set_password_url = token_step["Location"]

    form_page = client.get(set_password_url)
    assert form_page.status_code == 200

    confirm = client.post(
        set_password_url,
        {"new_password1": "new-pass-456", "new_password2": "new-pass-456"},
    )
    assert confirm.status_code == 302

    user.refresh_from_db()
    assert user.check_password("new-pass-456")

    login = client.post(
        reverse("accounts:login"),
        {"username": "david@example.com", "password": "new-pass-456"},
    )
    assert login.status_code == 302


@pytest.mark.django_db
def test_password_reset_email_uses_request_host(client, user):
    user.email = "david@example.com"
    user.save(update_fields=["email"])

    for host in ("leaderlodge.com", "www.leaderlodge.com"):
        mail.outbox.clear()
        client.post(
            reverse("accounts:password_reset"),
            {"email": "david@example.com"},
            HTTP_HOST=host,
            secure=True,
        )
        assert f"https://{host}/accounts/reset/" in mail.outbox[0].body


@pytest.mark.django_db
def test_signup_page_linked_from_login(client):
    content = client.get(reverse("accounts:login")).content.decode()
    assert reverse("accounts:signup") in content
    assert reverse("accounts:password_reset") in content
