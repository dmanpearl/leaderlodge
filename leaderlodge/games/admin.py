from django.contrib import admin

from leaderlodge.games.models import Game, GameParticipantResult


class GameParticipantResultInline(admin.TabularInline):
    model = GameParticipantResult
    extra = 0


@admin.register(Game)
class GameAdmin(admin.ModelAdmin):
    list_display = (
        "game_type_code",
        "group",
        "played_on",
        "player_count",
        "recorded_by",
    )
    list_filter = ("game_type_code", "played_on")
    inlines = [GameParticipantResultInline]


@admin.register(GameParticipantResult)
class GameParticipantResultAdmin(admin.ModelAdmin):
    list_display = ("game", "player", "score", "result", "placement")
    list_filter = ("result",)
