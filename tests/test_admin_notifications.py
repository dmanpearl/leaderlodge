from unittest import mock

import pytest
from django.contrib.auth.models import User
from django.core import mail
from django.core.management import call_command
from django.urls import reverse

from leaderlodge.accounts.honeypot import honeypot_post_data
from leaderlodge.core.admin_notification_registry import (
    DEFAULT_NOTIFICATIONS,
)
from leaderlodge.core.admin_notifications import (
    notify_admin_signup,
    resolved_notifications,
)
from leaderlodge.core.models import SiteSettings
from leaderlodge.feedback.models import Feedback
from leaderlodge.games.score_changes import apply_game_edits
from leaderlodge.groups.services import create_group_with_owner

TEST_NOTIFY_EMAIL = "ops@example.com"


@pytest.fixture
def site_settings(db):
    return SiteSettings.objects.create(
        singleton_key="",
        notify_email=TEST_NOTIFY_EMAIL,
        notifications=dict(DEFAULT_NOTIFICATIONS),
    )


@pytest.fixture
def user(db):
    return User.objects.create_user(
        username="david",
        email="david@example.com",
        password="test-pass-123",
        first_name="David",
    )


@pytest.mark.django_db
def test_setup_site_settings_command_creates_defaults():
    call_command("setup_site_settings", email=TEST_NOTIFY_EMAIL)
    config = SiteSettings.load()
    assert config.notify_email == TEST_NOTIFY_EMAIL
    assert resolved_notifications(config.notifications) == DEFAULT_NOTIFICATIONS


@pytest.mark.django_db
def test_resolved_notifications_merges_stored_values(site_settings):
    site_settings.notifications = {"signup": False, "feedback": True}
    site_settings.save(update_fields=["notifications"])
    flags = resolved_notifications(site_settings.notifications)
    assert flags["signup"] is False
    assert flags["feedback"] is True
    assert flags["invite_sent"] is False


@pytest.mark.django_db
def test_notify_admin_skipped_when_disabled(site_settings):
    site_settings.notifications = {key: False for key in DEFAULT_NOTIFICATIONS}
    site_settings.save(update_fields=["notifications"])
    sent = notify_admin_signup(user=User.objects.create_user(username="pat"))
    assert sent is False
    assert len(mail.outbox) == 0


@pytest.mark.django_db
def test_notify_admin_skipped_when_email_missing(site_settings, user):
    site_settings.notify_email = ""
    site_settings.save(update_fields=["notify_email"])
    assert notify_admin_signup(user=user) is False
    assert len(mail.outbox) == 0


@pytest.mark.django_db
@mock.patch("leaderlodge.core.geoip._lookup_ip_http")
def test_signup_notification_includes_location(mock_lookup, client, site_settings):
    from leaderlodge.core.geoip import GeoLookup

    mock_lookup.return_value = GeoLookup(
        city="Istanbul",
        region="Istanbul",
        country="Turkey",
        timezone="Europe/Istanbul",
    )
    client.post(
        reverse("accounts:signup"),
        honeypot_post_data(
            {
                "email": "newplayer@example.com",
                "first_name": "New",
                "password1": "strong-pass-123",
                "password2": "strong-pass-123",
            }
        ),
        REMOTE_ADDR="31.40.204.182",
    )
    signup_email = next(
        message
        for message in mail.outbox
        if "new user signup" in message.subject.lower()
    )
    assert "Location: Istanbul, Turkey" in signup_email.body
    assert "Timezone: Europe/Istanbul" in signup_email.body


@pytest.mark.django_db
def test_feedback_create_notifies_admin(client, site_settings, user, settings):
    settings.CSRF_TRUSTED_ORIGINS = ["https://leaderlodge.com"]
    client.force_login(user)
    response = client.post(
        reverse("feedback:create"),
        {
            "feedback_type": Feedback.FeedbackType.BUG,
            "game_type_code": "",
            "title": "Button stuck",
            "description": "Submit does nothing on mobile.",
        },
    )
    assert response.status_code == 302
    admin_messages = [
        message for message in mail.outbox if TEST_NOTIFY_EMAIL in message.to
    ]
    assert len(admin_messages) == 1
    assert "feedback submitted" in admin_messages[0].subject.lower()
    assert "Button stuck" in admin_messages[0].body
    feedback = Feedback.objects.get()
    expected_admin_url = (
        f"https://leaderlodge.com/admin/feedback/feedback/{feedback.pk}/change/"
    )
    assert expected_admin_url in admin_messages[0].body


@pytest.mark.django_db
def test_apply_game_edits_notifies_admin(site_settings, user):
    from django.utils import timezone

    from leaderlodge.games.models import Game, GameParticipantResult

    group = create_group_with_owner(user=user, name="Dom Club")
    from leaderlodge.groups.services import add_guest_player

    add_guest_player(group=group, display_name="Pat")
    players = list(group.players.order_by("pk"))
    game = Game.objects.create(
        group=group,
        game_type_code="dominos",
        played_on=timezone.localdate(),
        recorded_by=user,
        player_count=2,
    )
    GameParticipantResult.objects.create(
        game=game,
        player=players[0],
        score=30,
        result=GameParticipantResult.Result.WIN,
        placement=0,
    )
    GameParticipantResult.objects.create(
        game=game,
        player=players[1],
        score=20,
        result=GameParticipantResult.Result.PLAYED,
        placement=1,
    )
    mail.outbox.clear()
    apply_game_edits(
        game=game,
        user=user,
        notes="Corrected score from sheet",
        score_updates={players[1].pk: 35},
    )
    admin_messages = [
        message for message in mail.outbox if TEST_NOTIFY_EMAIL in message.to
    ]
    assert len(admin_messages) == 1
    assert "game edited" in admin_messages[0].subject.lower()


@pytest.mark.django_db
def test_notify_admin_send_failure_logs_warning_not_traceback(
    site_settings, user, caplog
):
    import logging
    from unittest.mock import patch

    caplog.set_level(logging.WARNING)
    with patch(
        "leaderlodge.core.admin_notifications.EmailMultiAlternatives.send",
        side_effect=Exception("SMTPAuthenticationError: auth failed"),
    ):
        assert notify_admin_signup(user=user) is False

    assert len(caplog.records) == 1
    record = caplog.records[0]
    assert record.levelname == "WARNING"
    assert "Admin notification signup failed" in record.message
    assert "SMTPAuthenticationError" in record.message
    assert record.exc_info is None


@pytest.mark.django_db
def test_site_settings_load_creates_empty_email(db):
    config = SiteSettings.load()
    assert config.notify_email == ""
    assert config.notifications == {}
