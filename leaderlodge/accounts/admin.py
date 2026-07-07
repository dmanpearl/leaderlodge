from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User

from leaderlodge.accounts.models import AuthEvent, UserProfile


def _log_user_status_changes(request, users, *, event_type) -> None:
    from leaderlodge.accounts.auth_log import record_auth_event

    for user in users:
        record_auth_event(
            event_type=event_type,
            request=request,
            user=user,
            email=user.email or "",
            source="admin",
            metadata={"acted_by": request.user.get_username()},
        )


@admin.action(description="Activate selected users")
def activate_users(modeladmin, request, queryset):
    affected = list(queryset.filter(is_active=False))
    updated = queryset.update(is_active=True)
    _log_user_status_changes(
        request,
        affected,
        event_type=AuthEvent.EventType.USER_ACTIVATED,
    )
    modeladmin.message_user(request, f"Activated {updated} user(s).")


@admin.action(description="Deactivate selected users")
def deactivate_users(modeladmin, request, queryset):
    targets = queryset.exclude(pk=request.user.pk)
    affected = list(targets.filter(is_active=True))
    updated = targets.update(is_active=False)
    _log_user_status_changes(
        request,
        affected,
        event_type=AuthEvent.EventType.USER_DEACTIVATED,
    )
    skipped_self = queryset.filter(pk=request.user.pk).exists()
    if updated:
        modeladmin.message_user(request, f"Deactivated {updated} user(s).")
    if skipped_self:
        modeladmin.message_user(
            request,
            "Your own account was not deactivated.",
            level=messages.WARNING,
        )
    if updated == 0 and not skipped_self:
        modeladmin.message_user(request, "No users were deactivated.")


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    extra = 0
    readonly_fields = ("email_verified",)
    fields = (
        "email_verified_at",
        "email_verified",
        "verification_email_sent_at",
        "ui_settings",
    )


class UserAdmin(BaseUserAdmin):
    inlines = [UserProfileInline]
    actions = (*BaseUserAdmin.actions, activate_users, deactivate_users)
    list_display = (
        "username",
        "email",
        "first_name",
        "last_name",
        "is_admin",
        "is_staff_column",
        "is_active",
        "email_verified_status",
    )

    @admin.display(boolean=True, description="Admin")
    def is_admin(self, obj):
        return obj.is_superuser

    @admin.display(boolean=True, description="Staff")
    def is_staff_column(self, obj):
        return obj.is_staff

    @admin.display(boolean=True, description="Email verified")
    def email_verified_status(self, obj):
        profile = getattr(obj, "profile", None)
        return profile is not None and profile.email_verified


admin.site.unregister(User)
admin.site.register(User, UserAdmin)


@admin.register(AuthEvent)
class AuthEventAdmin(admin.ModelAdmin):
    list_display = (
        "created_at",
        "event_type",
        "outcome",
        "user",
        "email",
        "ip_address",
        "source",
        "reason",
    )
    list_filter = (
        "event_type",
        "outcome",
        "source",
        "created_at",
    )
    search_fields = (
        "email",
        "ip_address",
        "reason",
        "user__username",
        "user__email",
    )
    readonly_fields = (
        "created_at",
        "event_type",
        "outcome",
        "user",
        "email",
        "ip_address",
        "user_agent",
        "source",
        "reason",
        "metadata",
    )
    date_hierarchy = "created_at"

    def has_add_permission(self, request) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        return request.user.is_superuser
