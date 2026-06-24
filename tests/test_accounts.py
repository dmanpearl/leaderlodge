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
    profile = UserProfile.objects.get(user=user)
    assert profile.email_verified_at is None


@pytest.mark.django_db
def test_signup_sends_welcome_email_with_verification_link(client):
    response = client.post(
        reverse("accounts:signup"),
        {
            "email": "newplayer@example.com",
            "password1": "strong-pass-123",
            "password2": "strong-pass-123",
        },
    )

    assert response.status_code == 302
    assert len(mail.outbox) == 1
    message = mail.outbox[0]
    assert message.to == ["newplayer@example.com"]
    assert "Welcome to LeaderLodge" in message.subject
    match = re.search(r"http://testserver(/accounts/verify/[^\s]+)", message.body)
    assert match is not None


@pytest.mark.django_db
def test_verify_email_confirm_marks_profile_verified(client):
    client.post(
        reverse("accounts:signup"),
        {
            "email": "verifyme@example.com",
            "password1": "strong-pass-123",
            "password2": "strong-pass-123",
        },
    )
    verify_url = re.search(
        r"http://testserver(/accounts/verify/[^\s]+)",
        mail.outbox[0].body,
    ).group(1)

    response = client.get(verify_url)
    assert response.status_code == 200
    assert "Email confirmed" in response.content.decode()

    profile = UserProfile.objects.get(user__email="verifyme@example.com")
    assert profile.email_verified_at is not None


@pytest.mark.django_db
def test_verify_email_confirm_rejects_invalid_token(client, user):
    from django.utils.encoding import force_bytes
    from django.utils.http import urlsafe_base64_encode

    user.email = "david@example.com"
    user.save(update_fields=["email"])
    uidb64 = urlsafe_base64_encode(force_bytes(user.pk))

    response = client.get(
        reverse(
            "accounts:verify_email_confirm",
            kwargs={"uidb64": uidb64, "token": "invalid-token"},
        )
    )

    assert response.status_code == 400
    assert user.profile.email_verified_at is None


@pytest.mark.django_db
def test_verify_email_page_resends_confirmation(client, user):
    user.email = "david@example.com"
    user.set_password("secret-pass")
    user.save(update_fields=["email", "password"])
    client.force_login(user)

    response = client.post(reverse("accounts:verify_email"))
    assert response.status_code == 302
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == ["david@example.com"]


@pytest.mark.django_db
def test_navbar_shows_account_name_in_mobile_dropdown(client, user):
    user.first_name = "David"
    user.save(update_fields=["first_name"])
    client.force_login(user)

    content = client.get(reverse("core:dashboard")).content.decode()

    assert 'class="dropdown-header mb-0">David</h6>' in content
    assert "d-md-none" in content


@pytest.mark.django_db
def test_navbar_shows_verify_email_for_unverified_user(client, user):
    user.email = "david@example.com"
    user.save(update_fields=["email"])
    client.force_login(user)

    content = client.get(reverse("core:dashboard")).content.decode()

    assert reverse("accounts:verify_email") in content
    assert "Verify Email" in content
    assert "Email verified" not in content


@pytest.mark.django_db
def test_navbar_shows_verified_status_for_verified_user(client, user):
    from django.utils import timezone

    user.email = "david@example.com"
    user.save(update_fields=["email"])
    user.profile.email_verified_at = timezone.now()
    user.profile.save(update_fields=["email_verified_at"])
    client.force_login(user)

    content = client.get(reverse("core:dashboard")).content.decode()

    assert "Email verified" in content
    assert reverse("accounts:verify_email") not in content


@pytest.mark.django_db
def test_changing_user_email_clears_verification(user):
    from django.utils import timezone

    user.email = "david@example.com"
    user.save(update_fields=["email"])
    user.profile.email_verified_at = timezone.now()
    user.profile.save(update_fields=["email_verified_at"])

    user.email = "newaddr@example.com"
    user.save(update_fields=["email"])

    user.profile.refresh_from_db()
    assert user.profile.email_verified_at is None


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
def test_anonymous_navbar_uses_account_dropdown(client):
    content = client.get(reverse("accounts:login")).content.decode()

    assert 'id="guestAccountMenu"' in content
    assert reverse("accounts:signup") in content
    assert reverse("accounts:login") in content
    assert 'btn btn-outline-light btn-sm' not in content


@pytest.mark.django_db
def test_signup_page_linked_from_login(client):
    content = client.get(reverse("accounts:login")).content.decode()
    assert reverse("accounts:signup") in content
    assert reverse("accounts:password_reset") in content
