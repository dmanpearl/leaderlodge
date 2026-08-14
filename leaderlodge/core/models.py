from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models


class AuditLog(models.Model):
    """Generic record of a sensitive or notable system event.

    event_type is a free-form string (not DB-enforced choices) so new
    event types can be added without a migration; see core/audit.py for
    the maintained registry of known types and the log_event() helper.
    """

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_log_entries",
    )
    event_type = models.CharField(max_length=64, db_index=True)
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    object_id = models.PositiveIntegerField(null=True, blank=True)
    target = GenericForeignKey("content_type", "object_id")
    payload = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    session_key = models.CharField(max_length=40, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
        indexes = [
            models.Index(fields=["event_type", "-created_at"]),
            models.Index(fields=["content_type", "object_id"]),
        ]
        verbose_name = "audit log entry"
        verbose_name_plural = "audit log entries"

    def __str__(self) -> str:
        return f"{self.event_type} by {self.actor or 'system'} at {self.created_at:%Y-%m-%d %H:%M}"


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
