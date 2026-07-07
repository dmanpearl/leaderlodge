import time

import pytest
from django.contrib.auth.models import User
from django.core import mail
from django.test import override_settings
from django.urls import reverse

from leaderlodge.accounts.honeypot import (
    HONEYPOT_FIELD,
    TIMING_FIELD,
    honeypot_post_data,
    honeypot_triggered,
)
from leaderlodge.core.admin_notification_registry import DEFAULT_NOTIFICATIONS
from leaderlodge.core.admin_notifications import notify_admin_signup_bot_blocked
from leaderlodge.core.models import SiteSettings
from leaderlodge.groups.services import create_group_with_owner


@pytest.fixture
def site_settings(db):
    return SiteSettings.objects.create(
        singleton_key="",
        notify_email="admin@example.com",
        notifications=dict(DEFAULT_NOTIFICATIONS),
    )


@pytest.mark.django_db
def test_honeypot_triggered_when_decoy_filled():
    triggered, reason = honeypot_triggered(
        {HONEYPOT_FIELD: "http://spam.example", TIMING_FIELD: "1"}
    )
    assert triggered is True
    assert reason == "honeypot_filled"


@pytest.mark.django_db
def test_honeypot_triggered_when_submitted_too_fast():
    triggered, reason = honeypot_triggered(
        {HONEYPOT_FIELD: "", TIMING_FIELD: str(int(time.time()))}
    )
    assert triggered is True
    assert reason == "submitted_too_fast"


@pytest.mark.django_db
@override_settings(HONEYPOT_ENABLED=True)
def test_signup_blocks_honeypot_and_notifies_admin(client, site_settings):
    response = client.post(
        reverse("accounts:signup"),
        honeypot_post_data(
            {
                "email": "bot@example.com",
                "password1": "strong-pass-123",
                "password2": "strong-pass-123",
                HONEYPOT_FIELD: "http://spam.example",
            }
        ),
    )

    assert response.status_code == 200
    assert "Unable to create your account" in response.content.decode()
    assert User.objects.filter(email="bot@example.com").count() == 0
    assert len(mail.outbox) == 1
    assert "signup blocked" in mail.outbox[0].subject.lower()


@pytest.mark.django_db
@override_settings(HONEYPOT_ENABLED=True)
def test_signup_allows_valid_honeypot_payload(client):
    response = client.post(
        reverse("accounts:signup"),
        honeypot_post_data(
            {
                "email": "real@example.com",
                "password1": "strong-pass-123",
                "password2": "strong-pass-123",
            }
        ),
    )

    assert response.status_code == 302
    assert User.objects.filter(email="real@example.com").exists()


@pytest.mark.django_db
@override_settings(HONEYPOT_ENABLED=False)
def test_signup_without_honeypot_fields_when_disabled(client):
    response = client.post(
        reverse("accounts:signup"),
        {
            "email": "open@example.com",
            "password1": "strong-pass-123",
            "password2": "strong-pass-123",
        },
    )

    assert response.status_code == 302
    assert User.objects.filter(email="open@example.com").exists()


@pytest.mark.django_db
def test_notify_admin_signup_bot_blocked_respects_toggle(site_settings, rf):
    site_settings.notifications = {"signup_bot_blocked": False}
    site_settings.save(update_fields=["notifications"])
    request = rf.post("/accounts/signup/")
    request.META["REMOTE_ADDR"] = "203.0.113.10"

    assert (
        notify_admin_signup_bot_blocked(
            request=request,
            source="signup",
            reason="honeypot_filled",
            email="bot@example.com",
        )
        is False
    )
    assert len(mail.outbox) == 0


@pytest.mark.django_db
@override_settings(HONEYPOT_ENABLED=True)
def test_invite_join_signup_blocks_honeypot(client, site_settings):
    owner = User.objects.create_user(username="owner", password="test-pass-123")
    group = create_group_with_owner(user=owner, name="Dom Club")
    from leaderlodge.groups.invites import create_email_invite

    invite = create_email_invite(
        group=group,
        email="guest@example.com",
        invited_by=owner,
    )

    response = client.post(
        reverse("groups:invite_accept", kwargs={"token": invite.token}),
        honeypot_post_data(
            {
                "email": invite.email,
                "first_name": "Guest",
                "password1": "strong-pass-123",
                "password2": "strong-pass-123",
                HONEYPOT_FIELD: "spam",
            }
        ),
    )

    assert response.status_code == 200
    assert User.objects.filter(email="guest@example.com").count() == 0
    assert len(mail.outbox) == 1
