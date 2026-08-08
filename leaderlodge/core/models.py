from django.db import models


class SiteSettings(models.Model):
    """Singleton site-wide settings (one row, keyed by singleton_key)."""

    singleton_key = models.CharField(
        max_length=1,
        unique=True,
        default="",
        editable=False,
    )
    notify_email = models.EmailField(
        blank=True,
        default="",
        help_text="Destination for admin notification emails.",
    )
    notifications = models.JSONField(
        default=dict,
        blank=True,
        help_text="Per-type notification toggles. Keys match admin_notification_registry.",
    )
    ai_game_entry_mic_enabled = models.BooleanField(
        default=False,
        help_text=(
            "Show an in-app microphone on Record Game AI entry (browser speech). "
            "Users can still tap the text field to type or use the system keyboard mic."
        ),
    )

    class Meta:
        verbose_name = "Site settings"
        verbose_name_plural = "Site settings"

    def __str__(self) -> str:
        return "Site settings"

    @classmethod
    def load(cls) -> "SiteSettings":
        obj, _created = cls.objects.get_or_create(singleton_key="")
        return obj
