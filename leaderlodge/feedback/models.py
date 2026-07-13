from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from leaderlodge.games.registry import GAME_TYPES


class Feedback(models.Model):
    class FeedbackType(models.TextChoices):
        BUG = "bug", "Bug report"
        FEATURE = "feature", "Feature request"
        SUGGESTION = "suggestion", "Suggestion"
        QUESTION = "question", "Question"
        COMMENT = "comment", "General comment"

    class Status(models.TextChoices):
        NEW = "new", "New"
        OPEN = "open", "Open"
        IN_PROGRESS = "in_progress", "In progress"
        RESOLVED = "resolved", "Resolved"
        CLOSED = "closed", "Closed"
        WONT_FIX = "wont_fix", "Won't fix"
        DEFERRED = "deferred", "Deferred"

    class Priority(models.TextChoices):
        LOW = "low", "Low"
        NORMAL = "normal", "Normal"
        HIGH = "high", "High"
        URGENT = "urgent", "Urgent"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="feedback_submissions",
    )
    feedback_type = models.CharField(
        max_length=20,
        choices=FeedbackType.choices,
    )
    game_type_code = models.CharField(
        max_length=30,
        blank=True,
        default="",
        help_text='Empty means "All games". Otherwise a code from the game registry.',
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.NEW,
    )
    priority = models.CharField(
        max_length=10,
        choices=Priority.choices,
        default=Priority.NORMAL,
    )
    is_visible = models.BooleanField(
        default=False,
        help_text="When enabled, feedback may be shown on a public roadmap.",
    )
    is_approved = models.BooleanField(
        default=False,
        help_text="Staff reviewed and accepted as valid feedback.",
    )
    read_at = models.DateTimeField(null=True, blank=True)
    responded_at = models.DateTimeField(null=True, blank=True)
    internal_notes = models.TextField(blank=True)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="assigned_feedback",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
        indexes = [
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["user", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.get_feedback_type_display()}: {self.title}"

    def clean(self) -> None:
        if self.game_type_code and self.game_type_code not in GAME_TYPES:
            raise ValidationError(
                {
                    "game_type_code": "Choose a valid game type or leave blank for all games."
                }
            )

    @property
    def game_type_label(self) -> str:
        if not self.game_type_code:
            return "All games"
        game_type = GAME_TYPES.get(self.game_type_code)
        return game_type.name if game_type else self.game_type_code
