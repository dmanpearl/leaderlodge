import logging

from django.conf import settings
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.core.mail import EmailMultiAlternatives
from django.template import loader
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from leaderlodge.accounts.models import UserProfile

logger = logging.getLogger(__name__)


class EmailVerificationTokenGenerator(PasswordResetTokenGenerator):
    def _make_hash_value(self, user, timestamp):
        try:
            verified_at = user.profile.email_verified_at
        except UserProfile.DoesNotExist:
            verified_at = None
        verified_part = verified_at.isoformat() if verified_at else ""
        return f"{user.pk}{user.email}{timestamp}{verified_part}"


email_verification_token_generator = EmailVerificationTokenGenerator()


def is_email_verified(user) -> bool:
    profile = getattr(user, "profile", None)
    if profile is None:
        return False
    return profile.email_verified_at is not None


def verification_email_pending(user) -> bool:
    profile = getattr(user, "profile", None)
    if profile is None:
        return False
    return (
        profile.verification_email_sent_at is not None
        and profile.email_verified_at is None
    )


def should_auto_send_verification(user) -> bool:
    profile = getattr(user, "profile", None)
    if profile is None:
        return True
    return profile.verification_email_sent_at is None


def record_verification_email_sent(user) -> None:
    profile = user.profile
    profile.verification_email_sent_at = timezone.now()
    profile.save(update_fields=["verification_email_sent_at"])


def mark_email_verified(user) -> None:
    profile = user.profile
    if profile.email_verified_at is None:
        profile.email_verified_at = timezone.now()
        profile.save(update_fields=["email_verified_at"])


def build_verification_url(request, user) -> str:
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = email_verification_token_generator.make_token(user)
    path = reverse(
        "accounts:verify_email_confirm",
        kwargs={"uidb64": uid, "token": token},
    )
    return request.build_absolute_uri(path)


def send_welcome_email(*, request, user) -> None:
    if not user.email:
        logger.warning("Skipped welcome email for user pk %s: no email on file", user.pk)
        raise ValueError("User has no email address on file.")

    verify_url = build_verification_url(request, user)
    context = {
        "user": user,
        "verify_url": verify_url,
    }
    subject = loader.render_to_string("accounts/welcome_subject.txt", context)
    subject = "".join(subject.splitlines())
    body = loader.render_to_string("accounts/welcome_email.txt", context)
    email_message = EmailMultiAlternatives(
        subject,
        body,
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
    )
    try:
        email_message.send()
        logger.info("Sent welcome email to %s for user pk %s", user.email, user.pk)
    except Exception:
        logger.exception("Welcome email delivery failed for user pk %s", user.pk)
        raise
