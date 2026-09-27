from django.contrib import admin
from django.db.models import Max
from django.forms.models import BaseInlineFormSet
from django.utils.html import format_html

from leaderlodge.games.models import Game, GameParticipantResult, GameScoreChangeLog
from leaderlodge.games.snapshot_diff import format_snapshot_diff
from leaderlodge.games.registry import get_game_type
from leaderlodge.games.validators import validate_participant_results
from leaderlodge.groups.locations import location_admin_label
from leaderlodge.groups.models import Group, Location

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
        "event",
        "game_label",
        "changed_by",
        "created_at",
    )
    list_filter = ("event", "created_at")
    search_fields = (
        "game__pk",
        "changed_by__username",
        "notes",
    )
    readonly_fields = (
        "event",
        "game",
        "changed_by",
        "created_at",
        "notes",
        "old_snapshot",
        "new_snapshot",
        "differences",
    )
    fieldsets = (
        (
            "Audit",
            {
                "fields": (
                    "event",
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
                    "differences",
                )
            },
        ),
    )

    @admin.display(description="Differences")
    def differences(self, obj: GameScoreChangeLog) -> str:
        text = format_snapshot_diff(obj.old_snapshot or {}, obj.new_snapshot or {})
        return format_html(
            "<pre style='white-space: pre-wrap; margin: 0;'>{}</pre>",
            text,
        )

    @admin.display(description="Game")
    def game_label(self, obj: GameScoreChangeLog) -> str:
        if obj.game_id:
            return str(obj.game)
        snapshot = obj.old_snapshot or {}
        game_id = snapshot.get("game_id")
        game_type = snapshot.get("game_type_code") or "game"
        played_on = snapshot.get("played_on") or ""
        if game_id:
            return f"Deleted {game_type} #{game_id} ({played_on})"
        return f"Deleted {game_type} ({played_on})" if played_on else "Deleted game"

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
        "location_display",
        "player_count",
        "recorded_by",
    )
    list_filter = ("game_type_code", "played_on", RecentActiveGroupFilter)
    search_fields = (
        "group__name",
        "group__pk",
    )
    inlines = [GameParticipantResultInline]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("location__library")

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        formfield = super().formfield_for_foreignkey(db_field, request, **kwargs)
        if db_field.name == "location":
            formfield.queryset = Location.objects.select_related("library").order_by(
                "library__name",
                "library__pk",
                "name",
            )
            formfield.label_from_instance = location_admin_label
        return formfield

    @admin.display(description="Location", ordering="location__name")
    def location_display(self, obj: Game) -> str:
        if obj.location_id is None:
            return "-"
        return location_admin_label(obj.location)


@admin.register(GameParticipantResult)
class GameParticipantResultAdmin(admin.ModelAdmin):
    list_display = ("game", "player", "score", "result", "placement")
    list_filter = ("result",)
