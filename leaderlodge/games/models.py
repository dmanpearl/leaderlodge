from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from leaderlodge.games.registry import get_game_type, normalize_score_type
from leaderlodge.games.validators import validate_participant_results


class Game(models.Model):
    group = models.ForeignKey(
        "groups.Group",
        on_delete=models.CASCADE,
        related_name="games",
    )
    game_type_code = models.CharField(max_length=30)
    played_on = models.DateField()
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="recorded_games",
    )
    notes = models.TextField(blank=True)
    player_count = models.PositiveSmallIntegerField()
    double_weight = models.PositiveSmallIntegerField(default=1)
    half_weight = models.PositiveSmallIntegerField(default=1)
    score_type = models.CharField(max_length=20, blank=True, default="")
    location = models.ForeignKey(
        "groups.Location",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="games",
    )
    import_source = models.CharField(max_length=64, blank=True)
    import_row_key = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-played_on", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["group", "import_source", "import_row_key"],
                condition=models.Q(
                    import_source__gt="",
                    import_row_key__gt="",
                ),
                name="unique_game_import_key",
            ),
        ]

    def __str__(self) -> str:
        game_type = get_game_type(self.game_type_code)
        return f"{game_type.name} on {self.played_on}"

    @property
    def game_type(self):
        return get_game_type(self.game_type_code)

    def clean(self) -> None:
        game_type = get_game_type(self.game_type_code)
        if self.score_type:
            self.score_type = normalize_score_type(
                self.game_type_code,
                self.score_type,
            )
        elif game_type.score_types:
            self.score_type = normalize_score_type(self.game_type_code, "")

    def validate_participant_results(self) -> None:
        results = list(self.participant_results.all())
        if not results:
            return
        validate_participant_results(
            game_type=get_game_type(self.game_type_code),
            results=[row.result for row in results],
        )


class GameParticipantResult(models.Model):
    class Result(models.TextChoices):
        WIN = "win", "Win"
        LOSS = "loss", "Loss"
        TIE = "tie", "Tie"
        PLAYED = "played", "Played"

    game = models.ForeignKey(
        Game,
        on_delete=models.CASCADE,
        related_name="participant_results",
    )
    player = models.ForeignKey(
        "groups.GroupPlayer",
        on_delete=models.PROTECT,
        related_name="game_results",
    )
    score = models.IntegerField(default=0)
    result = models.CharField(
        max_length=10,
        choices=Result.choices,
        default=Result.PLAYED,
    )
    placement = models.PositiveSmallIntegerField(null=True, blank=True)

    class Meta:
        unique_together = [("game", "player")]
        ordering = ["placement", "-score"]

    def __str__(self) -> str:
        return f"{self.player.display_name}: {self.result}"

    def clean(self) -> None:
        if self.player.group_id != self.game.group_id:
            raise ValidationError("Player must belong to the same group as the game.")
        if self.result == self.Result.LOSS:
            game_type = get_game_type(self.game.game_type_code)
            if not game_type.supports_loser:
                self.result = self.Result.PLAYED


class GameScoreChangeLog(models.Model):
    class Event(models.TextChoices):
        CHANGE = "change", "Change"
        DELETE = "delete", "Delete"

    game = models.ForeignKey(
        Game,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="score_change_logs",
    )
    event = models.CharField(
        max_length=10,
        choices=Event.choices,
        default=Event.CHANGE,
    )
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="game_score_changes",
        verbose_name="changed by",
    )
    notes = models.TextField()
    old_snapshot = models.JSONField()
    new_snapshot = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
        verbose_name = "game edit log"
        verbose_name_plural = "game edit logs"

    def __str__(self) -> str:
        game_ref = self.game_id or self.old_snapshot.get("game_id") or "?"
        return f"Game {game_ref} {self.event} by {self.changed_by}"
