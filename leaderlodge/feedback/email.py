import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template import loader

from leaderlodge.feedback.models import Feedback

logger = logging.getLogger(__name__)


def render_feedback_confirmation_email(*, feedback: Feedback) -> tuple[str, str]:
    context = {"feedback": feedback, "user": feedback.user}
    subject = loader.render_to_string(
        "feedback/feedback_confirmation_subject.txt",
        context,
    )
    subject = "".join(subject.splitlines())
    body = loader.render_to_string(
        "feedback/feedback_confirmation_email.txt",
        context,
    )
    return subject, body


def send_feedback_confirmation_email(*, feedback: Feedback) -> None:
    user = feedback.user
    if not user.email:
        logger.warning(
            "Skipped feedback confirmation for feedback pk %s: user pk %s has no email",
            feedback.pk,
            user.pk,
        )
        raise ValueError("User has no email address on file.")

    subject, body = render_feedback_confirmation_email(feedback=feedback)
    email_message = EmailMultiAlternatives(
        subject,
        body,
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
    )
    try:
        email_message.send()
        logger.info(
            "Sent feedback confirmation to %s for feedback pk %s",
            user.email,
            feedback.pk,
        )
    except Exception:
        logger.exception(
            "Feedback confirmation email failed for feedback pk %s", feedback.pk
        )
        raise
