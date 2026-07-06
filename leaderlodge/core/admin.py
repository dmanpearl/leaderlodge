from django.contrib import admin

from leaderlodge.core.admin_notification_registry import NOTIFICATION_LABELS
from leaderlodge.core.forms import SiteSettingsAdminForm
from leaderlodge.core.models import SiteSettings


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    form = SiteSettingsAdminForm
    readonly_fields = ["singleton_key"]

    def get_fieldsets(self, request, obj=None):
        fields = ["notify_email", *NOTIFICATION_LABELS.keys()]
        if obj is not None:
            fields = ["singleton_key", *fields]
        return [
            (
                "Admin notifications",
                {
                    "fields": fields,
                    "description": (
                        "Email destination and toggles for operator alerts. "
                        "New notification types can be added in code without a migration."
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
