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

    class Meta:
        verbose_name = "Site settings"
        verbose_name_plural = "Site settings"

    def __str__(self) -> str:
        return "Site settings"

    @classmethod
    def load(cls) -> "SiteSettings":
        obj, _created = cls.objects.get_or_create(singleton_key="")
        return obj
