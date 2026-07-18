import pytest
from django.contrib.auth.models import User
from django.core import mail
from django.core.management import call_command
from django.core.management.base import CommandError

from leaderlodge.core.brand import TAGLINE


@pytest.fixture
def user(db):
    return User.objects.create_user(
        username="david",
        email="david@example.com",
        password="test-pass-123",
    )


@pytest.mark.django_db
def test_send_sample_email_password_reset_print_only(user, capsys):
    call_command(
        "send_sample_email",
        "--type=password-reset",
        f"--user={user.username}",
        "--print-only",
    )
    captured = capsys.readouterr()
    assert "To: david@example.com" in captured.out
    assert TAGLINE not in captured.out
    assert "/accounts/reset/" in captured.out
    assert len(mail.outbox) == 0


@pytest.mark.django_db
def test_send_sample_email_sends_welcome(user):
    call_command(
        "send_sample_email",
        "--type=welcome",
        f"--user={user.username}",
    )

    assert len(mail.outbox) == 1
    message = mail.outbox[0]
    assert message.to == ["david@example.com"]
    assert TAGLINE in message.body


@pytest.mark.django_db
def test_send_sample_email_allows_recipient_override(user):
    call_command(
        "send_sample_email",
        "--type=password-reset",
        f"--user={user.username}",
        "--to=other@example.com",
    )

    assert mail.outbox[0].to == ["other@example.com"]


@pytest.mark.django_db
def test_send_sample_email_requires_email_or_to(user):
    user.email = ""
    user.save(update_fields=["email"])

    with pytest.raises(CommandError, match="Pass --to explicitly"):
        call_command(
            "send_sample_email",
            "--type=welcome",
            f"--user={user.username}",
        )
