from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User

from leaderlodge.accounts.models import UserProfile


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
