from django.contrib import admin

from leaderlodge.core.admin_notification_registry import NOTIFICATION_LABELS
from leaderlodge.core.forms import SiteSettingsAdminForm
from leaderlodge.core.models import AuditLog, SiteSettings


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ["created_at", "event_type", "actor", "target", "ip_address"]
    list_filter = ["event_type"]
    search_fields = ["actor__username", "event_type", "ip_address"]
    date_hierarchy = "created_at"
    readonly_fields = [
        "actor",
        "event_type",
        "content_type",
        "object_id",
        "target",
        "payload",
        "ip_address",
        "session_key",
        "created_at",
    ]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    form = SiteSettingsAdminForm
    readonly_fields = ["singleton_key"]

    def get_fieldsets(self, request, obj=None):
        notify_fields = ["notify_email", *NOTIFICATION_LABELS.keys()]
        if obj is not None:
            notify_fields = ["singleton_key", *notify_fields]
        return [
            (
                "Admin notifications",
                {
                    "fields": notify_fields,
                    "description": (
                        "Email destination and toggles for operator alerts. "
                        "New notification types can be added in code without a migration."
                    ),
                },
            ),
            (
                "Record Game AI",
                {
                    "fields": ["ai_game_entry_mic_enabled"],
                    "description": (
                        "Experimental in-app mic for AI game entry. "
                        "Uses browser speech; quality varies by device "
                        "(often weaker on iPhone Safari than the keyboard mic)."
                    ),
                },
            ),
        ]

    def has_add_permission(self, request):
        if SiteSettings.objects.exists():
            return False
        return super().has_add_permission(request)

    def has_delete_permission(self, request, obj=None):
        return False
