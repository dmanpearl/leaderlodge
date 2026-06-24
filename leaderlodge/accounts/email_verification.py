import logging

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
        return

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
        None,
        [user.email],
    )
    try:
        email_message.send()
        logger.info("Sent welcome email to user pk %s", user.pk)
    except Exception:
        logger.exception("Welcome email delivery failed for user pk %s", user.pk)
        raise
