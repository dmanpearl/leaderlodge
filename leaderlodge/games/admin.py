from django.contrib import admin
from django.forms.models import BaseInlineFormSet

from leaderlodge.games.models import Game, GameParticipantResult, GameScoreChangeLog
from leaderlodge.games.registry import get_game_type
from leaderlodge.games.validators import validate_participant_results


class GameParticipantResultInlineFormSet(BaseInlineFormSet):
    def clean(self) -> None:
        super().clean()
        if any(form.errors for form in self.forms):
            return

        game_type_code = self.instance.game_type_code
        if not game_type_code:
            return

        game_type = get_game_type(game_type_code)
        participant_results: list[str] = []
        for form in self.forms:
            if not form.cleaned_data or form.cleaned_data.get("DELETE"):
                continue
            result = form.cleaned_data.get("result")
            if (
                not game_type.supports_loser
                and result == GameParticipantResult.Result.LOSS
            ):
                result = GameParticipantResult.Result.PLAYED
                form.cleaned_data["result"] = result
            participant_results.append(result)

        if not participant_results:
            return

        validate_participant_results(
            game_type=game_type,
            results=participant_results,
        )


class GameParticipantResultInline(admin.TabularInline):
    model = GameParticipantResult
    extra = 0
    formset = GameParticipantResultInlineFormSet


@admin.register(GameScoreChangeLog)
class GameScoreChangeLogAdmin(admin.ModelAdmin):
    list_display = (
        "game",
        "player",
        "change_type",
        "old_score",
        "new_score",
        "changed_by",
        "created_at",
    )
    list_filter = ("change_type", "game__game_type_code", "created_at")
    search_fields = (
        "game__pk",
        "player__display_name",
        "changed_by__username",
        "notes",
    )
    readonly_fields = (
        "game",
        "participant_result",
        "player",
        "changed_by",
        "notes",
        "change_type",
        "old_score",
        "new_score",
        "old_result",
        "new_result",
        "old_placement",
        "new_placement",
        "old_double_weight",
        "new_double_weight",
        "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(Game)
class GameAdmin(admin.ModelAdmin):
    list_display = (
        "game_type_code",
        "group",
        "played_on",
        "location",
        "player_count",
        "recorded_by",
    )
    list_filter = ("game_type_code", "played_on")
    inlines = [GameParticipantResultInline]


@admin.register(GameParticipantResult)
class GameParticipantResultAdmin(admin.ModelAdmin):
    list_display = ("game", "player", "score", "result", "placement")
    list_filter = ("result",)
