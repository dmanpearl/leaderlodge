from django.core.management.base import BaseCommand, CommandError

from leaderlodge.core.admin_notification_registry import DEFAULT_NOTIFICATIONS
from leaderlodge.core.models import SiteSettings


class Command(BaseCommand):
    help = (
        "Create or update the site settings singleton with admin notification "
        "toggles and the notify email address."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--email",
            required=True,
            help="Admin notification email (required).",
        )

    def handle(self, *args, **options):
        email = options["email"].strip()
        if not email:
            raise CommandError("--email is required and cannot be blank.")

        config, created = SiteSettings.objects.get_or_create(
            singleton_key="",
            defaults={
                "notify_email": email,
                "notifications": dict(DEFAULT_NOTIFICATIONS),
            },
        )
        if not created:
            config.notify_email = email
            if not config.notifications:
                config.notifications = dict(DEFAULT_NOTIFICATIONS)
            config.save(update_fields=["notify_email", "notifications"])

        action = "Created" if created else "Updated"
        self.stdout.write(
            self.style.SUCCESS(
                f"{action} site settings: notify_email={config.notify_email}"
            )
        )
