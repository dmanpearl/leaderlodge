from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User

from leaderlodge.accounts.models import UserProfile


@admin.action(description="Activate selected users")
def activate_users(modeladmin, request, queryset):
    updated = queryset.update(is_active=True)
    modeladmin.message_user(request, f"Activated {updated} user(s).")


@admin.action(description="Deactivate selected users")
def deactivate_users(modeladmin, request, queryset):
    targets = queryset.exclude(pk=request.user.pk)
    updated = targets.update(is_active=False)
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
