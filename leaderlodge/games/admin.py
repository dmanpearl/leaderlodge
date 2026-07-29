from django.contrib import admin
from django.db.models import Max
from django.forms.models import BaseInlineFormSet

from leaderlodge.games.models import Game, GameParticipantResult, GameScoreChangeLog
from leaderlodge.games.registry import get_game_type
from leaderlodge.games.validators import validate_participant_results
from leaderlodge.groups.models import Group

RECENT_ACTIVE_GROUP_FILTER_LIMIT = 15


class RecentActiveGroupFilter(admin.SimpleListFilter):
    title = "group (recent)"
    parameter_name = "group"

    def lookups(self, request, model_admin):
        ranked_group_ids = (
            Game.objects.values("group_id")
            .annotate(
                latest_played_on=Max("played_on"),
                latest_created_at=Max("created_at"),
            )
            .order_by("-latest_played_on", "-latest_created_at", "group_id")
            .values_list("group_id", flat=True)[:RECENT_ACTIVE_GROUP_FILTER_LIMIT]
        )
        groups = Group.objects.in_bulk(ranked_group_ids)
        return [
            (str(group_id), groups[group_id].name)
            for group_id in ranked_group_ids
            if group_id in groups
        ]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(group_id=self.value())
        return queryset


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
        "changed_by",
        "created_at",
    )
    list_filter = ("game__game_type_code", "created_at")
    search_fields = (
        "game__pk",
        "changed_by__username",
        "notes",
    )
    readonly_fields = (
        "game",
        "changed_by",
        "created_at",
        "notes",
        "old_snapshot",
        "new_snapshot",
    )
    fieldsets = (
        (
            "Audit",
            {
                "fields": (
                    "game",
                    "changed_by",
                    "created_at",
                    "notes",
                )
            },
        ),
        (
            "Snapshots",
            {
                "fields": (
                    "old_snapshot",
                    "new_snapshot",
                )
            },
        ),
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
    list_filter = ("game_type_code", "played_on", RecentActiveGroupFilter)
    search_fields = (
        "group__name",
        "group__pk",
    )
    inlines = [GameParticipantResultInline]


@admin.register(GameParticipantResult)
class GameParticipantResultAdmin(admin.ModelAdmin):
    list_display = ("game", "player", "score", "result", "placement")
    list_filter = ("result",)
