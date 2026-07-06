from __future__ import annotations

from django.conf import settings
from django.db import models


class InsightLog(models.Model):
    class Source(models.TextChoices):
        ASK = "ask", "Ask the Lodge"
        PLAYER = "player", "Player insight"
        GROUP_LEADERBOARD = "group_leaderboard", "Group leaderboard"
        GROUP_HALL_OF_FAME = "group_hall_of_fame", "Hall of Fame"
        MATCHUP = "matchup", "Matchup"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="insight_logs",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    source = models.CharField(max_length=32, choices=Source.choices)
    preset = models.CharField(max_length=32, blank=True, default="")
    question = models.TextField(blank=True, default="")

    is_failure = models.BooleanField(default=False)
    http_status = models.PositiveSmallIntegerField(null=True, blank=True)
    error_message = models.TextField(blank=True, default="")
    answer_markdown = models.TextField(blank=True, default="")

    is_regenerate = models.BooleanField(default=False)
    regenerate_of = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="regenerations",
    )

    group = models.ForeignKey(
        "groups.Group",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="insight_logs",
    )
    player = models.ForeignKey(
        "groups.GroupPlayer",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="insight_logs",
    )
    game = models.ForeignKey(
        "games.Game",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="insight_logs",
    )
    game_type_code = models.CharField(max_length=30, blank=True, default="")
    period = models.JSONField(default=dict, blank=True)

    model_slug = models.CharField(max_length=64, blank=True, default="")
    prompt_version = models.PositiveSmallIntegerField(null=True, blank=True)
    cached = models.BooleanField(default=False)
    input_tokens = models.PositiveIntegerField(default=0)
    output_tokens = models.PositiveIntegerField(default=0)

    tools_used = models.JSONField(default=list, blank=True)
    coverage = models.JSONField(null=True, blank=True)
    context_summary = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
        indexes = [
            models.Index(fields=["is_failure", "created_at"]),
            models.Index(fields=["source", "created_at"]),
            models.Index(fields=["user", "created_at"]),
            models.Index(fields=["group", "created_at"]),
        ]

    def __str__(self) -> str:
        label = self.question[:60] if self.question else self.get_source_display()
        if self.is_failure:
            return f"Failed {self.get_source_display()}: {label}"
        return f"{self.get_source_display()}: {label}"
