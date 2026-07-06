from django.contrib import admin

from leaderlodge.insights.models import InsightLog


@admin.register(InsightLog)
class InsightLogAdmin(admin.ModelAdmin):
    list_display = (
        "created_at",
        "source",
        "user",
        "group",
        "question_preview",
        "is_failure",
        "is_regenerate",
        "cached",
        "model_slug",
    )
    list_filter = (
        "source",
        "is_failure",
        "is_regenerate",
        "cached",
        "created_at",
    )
    search_fields = (
        "question",
        "answer_markdown",
        "error_message",
        "user__username",
        "user__email",
        "group__name",
        "player__display_name",
    )
    readonly_fields = (
        "user",
        "created_at",
        "source",
        "preset",
        "question",
        "is_failure",
        "http_status",
        "error_message",
        "answer_markdown",
        "is_regenerate",
        "regenerate_of",
        "group",
        "player",
        "game",
        "game_type_code",
        "period",
        "model_slug",
        "prompt_version",
        "cached",
        "input_tokens",
        "output_tokens",
        "tools_used",
        "coverage",
        "context_summary",
    )
    autocomplete_fields = ("regenerate_of", "group", "player")
    fieldsets = (
        (
            "Request",
            {
                "fields": (
                    "created_at",
                    "user",
                    "source",
                    "preset",
                    "question",
                    "is_regenerate",
                    "regenerate_of",
                )
            },
        ),
        (
            "Outcome",
            {
                "fields": (
                    "is_failure",
                    "http_status",
                    "error_message",
                    "answer_markdown",
                )
            },
        ),
        (
            "Scope",
            {
                "fields": (
                    "group",
                    "player",
                    "game",
                    "game_type_code",
                    "period",
                    "context_summary",
                )
            },
        ),
        (
            "Model run",
            {
                "fields": (
                    "model_slug",
                    "prompt_version",
                    "cached",
                    "input_tokens",
                    "output_tokens",
                    "tools_used",
                    "coverage",
                )
            },
        ),
    )

    @admin.display(description="Question")
    def question_preview(self, obj: InsightLog) -> str:
        if not obj.question:
            return ""
        if len(obj.question) <= 80:
            return obj.question
        return f"{obj.question[:77]}..."

    def has_add_permission(self, request) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        return request.user.is_superuser
