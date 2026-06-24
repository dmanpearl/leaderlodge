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
    list_display = BaseUserAdmin.list_display + ("email_verified_status",)

    @admin.display(boolean=True, description="Email verified")
    def email_verified_status(self, obj):
        profile = getattr(obj, "profile", None)
        return profile is not None and profile.email_verified


admin.site.unregister(User)
admin.site.register(User, UserAdmin)
