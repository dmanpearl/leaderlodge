from django.contrib import admin
from django.utils import timezone

from leaderlodge.feedback.models import Feedback


@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "feedback_type",
        "status",
        "priority",
        "user",
        "game_type_code",
        "is_approved",
        "is_visible",
        "assigned_to",
        "created_at",
    )
    list_filter = (
        "feedback_type",
        "status",
        "priority",
        "is_approved",
        "is_visible",
        "game_type_code",
        "created_at",
    )
    search_fields = (
        "title",
        "description",
        "user__username",
        "user__email",
        "internal_notes",
    )
    readonly_fields = ("created_at", "updated_at")
    autocomplete_fields = ("user", "assigned_to")
    fieldsets = (
        (
            "Submission",
            {
                "fields": (
                    "user",
                    "feedback_type",
                    "game_type_code",
                    "title",
                    "description",
                    "created_at",
                    "updated_at",
                )
            },
        ),
        (
            "Triage",
            {
                "fields": (
                    "status",
                    "priority",
                    "is_approved",
                    "is_visible",
                    "assigned_to",
                    "read_at",
                    "responded_at",
                    "internal_notes",
                )
            },
        ),
    )

    def change_view(self, request, object_id, form_url="", extra_context=None):
        if request.method == "GET" and object_id:
            Feedback.objects.filter(pk=object_id, read_at__isnull=True).update(
                read_at=timezone.now()
            )
        return super().change_view(request, object_id, form_url, extra_context)
