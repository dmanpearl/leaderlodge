from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import EmailMultiAlternatives
from django.core.management.base import BaseCommand, CommandError

from leaderlodge.accounts.sample_email import mock_request, render_sample_email

User = get_user_model()


class Command(BaseCommand):
    help = (
        "Send or print sample welcome and password-reset emails for development "
        "validation."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--type",
            choices=["welcome", "password-reset"],
            required=True,
            help="Which transactional email template to render.",
        )
        parser.add_argument(
            "--user",
            required=True,
            help="Username of the account whose data appears in the email.",
        )
        parser.add_argument(
            "--to",
            help="Recipient address. Defaults to the user's email on file.",
        )
        parser.add_argument(
            "--site-url",
            default="http://127.0.0.1:8000",
            help="Base site URL used to build verification and reset links.",
        )
        parser.add_argument(
            "--print-only",
            action="store_true",
            help="Print subject and body to stdout without sending mail.",
        )

    def handle(self, *args, **options):
        user = self._resolve_user(options["user"])
        to_email = options["to"] or user.email
        if not to_email:
            raise CommandError(
                f"User {user.username!r} has no email on file. Pass --to explicitly."
            )

        request = mock_request(options["site_url"])
        subject, body = render_sample_email(
            email_type=options["type"],
            user=user,
            request=request,
        )

        if options["print_only"]:
            self._print_preview(to_email=to_email, subject=subject, body=body)
            return

        email_message = EmailMultiAlternatives(
            subject,
            body,
            settings.DEFAULT_FROM_EMAIL,
            [to_email],
        )
        email_message.send()
        self.stdout.write(
            self.style.SUCCESS(
                f"Sent {options['type']} email to {to_email} "
                f"via {settings.EMAIL_BACKEND}."
            )
        )

    def _resolve_user(self, username: str):
        try:
            return User.objects.get(username=username)
        except User.DoesNotExist as exc:
            raise CommandError(f"No user with username {username!r}.") from exc

    def _print_preview(self, *, to_email: str, subject: str, body: str) -> None:
        self.stdout.write(f"To: {to_email}")
        self.stdout.write(f"From: {settings.DEFAULT_FROM_EMAIL}")
        self.stdout.write(f"Subject: {subject}")
        self.stdout.write("")
        self.stdout.write(body)
