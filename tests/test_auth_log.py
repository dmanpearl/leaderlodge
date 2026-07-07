import re

import pytest
from django.contrib.auth.models import User
from django.core import mail
from django.test import RequestFactory, override_settings
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from leaderlodge.accounts import auth_log
from leaderlodge.accounts.auth_log import record_auth_event
from leaderlodge.accounts.honeypot import HONEYPOT_FIELD, honeypot_post_data
from leaderlodge.accounts.models import AuthEvent
from leaderlodge.core.admin_notification_registry import DEFAULT_NOTIFICATIONS
from leaderlodge.core.models import SiteSettings
from leaderlodge.groups.invites import (
    accept_group_invite,
    create_email_invite,
    send_invite_email,
)
from leaderlodge.groups.services import create_group_with_owner


@pytest.fixture
def site_settings(db):
    return SiteSettings.objects.create(
        singleton_key="",
        notify_email="admin@example.com",
        notifications=dict(DEFAULT_NOTIFICATIONS),
    )


@pytest.mark.django_db
def test_record_auth_event_default_outcomes():
    success = record_auth_event(event_type=AuthEvent.EventType.SIGNUP)
    blocked = record_auth_event(event_type=AuthEvent.EventType.SIGNUP_BLOCKED)
    failed = record_auth_event(event_type=AuthEvent.EventType.LOGIN_FAILED)

    assert success.outcome == AuthEvent.Outcome.SUCCESS
    assert blocked.outcome == AuthEvent.Outcome.BLOCKED
    assert failed.outcome == AuthEvent.Outcome.FAILURE


@pytest.mark.django_db
def test_signup_records_auth_event(client):
    response = client.post(
        reverse("accounts:signup"),
        honeypot_post_data(
            {
                "email": "newplayer@example.com",
                "password1": "strong-pass-123",
                "password2": "strong-pass-123",
            }
        ),
    )

    assert response.status_code == 302
    event = AuthEvent.objects.get(event_type=AuthEvent.EventType.SIGNUP)
    assert event.email == "newplayer@example.com"
    assert event.source == "signup"
    assert event.user is not None


@pytest.mark.django_db
@override_settings(HONEYPOT_ENABLED=True)
def test_bot_blocked_records_event_and_emails_admin_link(client, site_settings):
    response = client.post(
        reverse("accounts:signup"),
        honeypot_post_data(
            {
                "email": "bot@example.com",
                "first_name": "Spam",
                "last_name": "Bot",
                "password1": "strong-pass-123",
                "password2": "strong-pass-123",
                HONEYPOT_FIELD: "http://spam.example",
            }
        ),
    )

    assert response.status_code == 200
    event = AuthEvent.objects.get(event_type=AuthEvent.EventType.SIGNUP_BLOCKED)
    assert event.reason == "honeypot_filled"
    assert event.metadata == {
        "first_name": "Spam",
        "last_name": "Bot",
        "trap_value": "http://spam.example",
    }
    assert User.objects.filter(email="bot@example.com").count() == 0
    assert len(mail.outbox) == 1
    body = mail.outbox[0].body
    change_path = reverse("admin:accounts_authevent_change", args=[event.pk])
    assert change_path in body
    assert "First name: Spam" in body


@pytest.mark.django_db
def test_failed_signup_records_event(client):
    response = client.post(
        reverse("accounts:signup"),
        honeypot_post_data(
            {
                "email": "not-an-email",
                "password1": "x",
                "password2": "y",
            }
        ),
    )

    assert response.status_code == 200
    event = AuthEvent.objects.get(event_type=AuthEvent.EventType.SIGNUP_FAILED)
    assert event.outcome == AuthEvent.Outcome.FAILURE
    assert event.source == "signup"


@pytest.mark.django_db
def test_failed_signup_switch_off(client, monkeypatch):
    monkeypatch.setattr(auth_log, "LOG_FAILED_SIGNUPS", False)
    client.post(
        reverse("accounts:signup"),
        honeypot_post_data(
            {
                "email": "not-an-email",
                "password1": "x",
                "password2": "y",
            }
        ),
    )

    assert not AuthEvent.objects.filter(
        event_type=AuthEvent.EventType.SIGNUP_FAILED
    ).exists()


@pytest.mark.django_db
def test_login_failure_records_event(client):
    User.objects.create_user(username="dave", password="right-pass-123")
    client.post(
        reverse("accounts:login"),
        {"username": "dave", "password": "wrong-pass"},
    )

    event = AuthEvent.objects.get(event_type=AuthEvent.EventType.LOGIN_FAILED)
    assert event.outcome == AuthEvent.Outcome.FAILURE
    assert event.user is not None
    assert event.reason == "bad_credentials"


@pytest.mark.django_db
def test_password_reset_request_records_event(client):
    User.objects.create_user(
        username="dave",
        email="dave@example.com",
        password="right-pass-123",
    )
    client.post(
        reverse("accounts:password_reset"),
        {"email": "dave@example.com"},
    )

    event = AuthEvent.objects.get(
        event_type=AuthEvent.EventType.PASSWORD_RESET_REQUESTED
    )
    assert event.email == "dave@example.com"
    assert event.source == "password_reset"


@pytest.mark.django_db
def test_password_reset_complete_records_event(client):
    from leaderlodge.accounts.forms import StyledSetPasswordForm

    user = User.objects.create_user(
        username="dave",
        email="dave@example.com",
        password="old-pass-123",
    )
    form = StyledSetPasswordForm(
        user,
        {"new_password1": "brand-new-pass-9", "new_password2": "brand-new-pass-9"},
    )
    assert form.is_valid()
    form.save()

    event = AuthEvent.objects.get(
        event_type=AuthEvent.EventType.PASSWORD_RESET_COMPLETED
    )
    assert event.user == user


@pytest.mark.django_db
def test_email_verified_records_event(client):
    from leaderlodge.accounts.email_verification import (
        email_verification_token_generator,
    )

    user = User.objects.create_user(
        username="dave",
        email="dave@example.com",
        password="right-pass-123",
    )
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = email_verification_token_generator.make_token(user)
    response = client.get(
        reverse(
            "accounts:verify_email_confirm",
            kwargs={"uidb64": uid, "token": token},
        )
    )

    assert response.status_code == 200
    assert AuthEvent.objects.filter(
        event_type=AuthEvent.EventType.EMAIL_VERIFIED, user=user
    ).exists()


@pytest.mark.django_db
def test_invite_sent_and_accepted_record_events():
    owner = User.objects.create_user(username="owner", password="test-pass-123")
    group = create_group_with_owner(user=owner, name="Dom Club")
    invite = create_email_invite(
        group=group,
        email="guest@example.com",
        invited_by=owner,
    )
    request = RequestFactory().get("/")
    send_invite_email(request=request, invite=invite)

    assert AuthEvent.objects.filter(event_type=AuthEvent.EventType.INVITE_SENT).exists()

    guest = User.objects.create_user(
        username="guest",
        email="guest@example.com",
        password="test-pass-123",
    )
    accept_group_invite(invite=invite, user=guest, first_name="Guest")

    assert AuthEvent.objects.filter(
        event_type=AuthEvent.EventType.INVITE_ACCEPTED, user=guest
    ).exists()


@pytest.mark.django_db
def test_admin_deactivate_records_event(client):
    admin_user = User.objects.create_superuser(
        username="root",
        email="root@example.com",
        password="admin-pass-123",
    )
    target = User.objects.create_user(username="victim", password="test-pass-123")
    client.force_login(admin_user)

    client.post(
        reverse("admin:auth_user_changelist"),
        {
            "action": "deactivate_users",
            "_selected_action": [str(target.pk)],
        },
    )

    target.refresh_from_db()
    assert target.is_active is False
    assert AuthEvent.objects.filter(
        event_type=AuthEvent.EventType.USER_DEACTIVATED, user=target
    ).exists()
