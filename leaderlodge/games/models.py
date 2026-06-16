from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from leaderlodge.games.registry import get_game_type


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
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-played_on", "-created_at"]

    def __str__(self) -> str:
        game_type = get_game_type(self.game_type_code)
        return f"{game_type.name} on {self.played_on}"

    @property
    def game_type(self):
        return get_game_type(self.game_type_code)

    def clean(self) -> None:
        get_game_type(self.game_type_code)
        results = list(self.participant_results.all())
        if not results:
            return

        winner_count = sum(
            1 for r in results if r.result == GameParticipantResult.Result.WIN
        )
        tie_count = sum(
            1 for r in results if r.result == GameParticipantResult.Result.TIE
        )
        loser_count = sum(
            1 for r in results if r.result == GameParticipantResult.Result.LOSS
        )
        game_type = get_game_type(self.game_type_code)
        game_type.validate(
            player_count=len(results),
            winner_count=winner_count,
            tie_count=tie_count,
            loser_count=loser_count,
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
