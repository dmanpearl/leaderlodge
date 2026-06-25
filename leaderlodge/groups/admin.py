from django.contrib import admin

from leaderlodge.groups.models import (
    Group,
    GroupInvite,
    GroupMembership,
    GroupPlayer,
    Location,
    LocationLibrary,
)


class GroupMembershipInline(admin.TabularInline):
    model = GroupMembership
    extra = 0


class GroupPlayerInline(admin.TabularInline):
    model = GroupPlayer
    extra = 0
    fields = ("display_name", "hide_from_game_list", "is_active", "linked_user")
    show_change_link = True


class LocationInline(admin.TabularInline):
    model = Location
    extra = 0
    fields = ("name", "normalized_name", "created_at")
    readonly_fields = ("normalized_name", "created_at")


@admin.register(LocationLibrary)
class LocationLibraryAdmin(admin.ModelAdmin):
    list_display = ("name", "created_by", "created_at", "group_count")
    search_fields = ("name",)
    inlines = [LocationInline]

    @admin.display(description="Groups")
    def group_count(self, obj):
        return obj.groups.count()


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ("name", "library", "created_at")
    list_filter = ("library",)
    search_fields = ("name",)


@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = ("name", "is_demo", "location_library", "created_by", "created_at")
    search_fields = ("name", "description")
    list_filter = ("is_demo", "location_library")
    inlines = [GroupMembershipInline, GroupPlayerInline]


@admin.register(GroupInvite)
class GroupInviteAdmin(admin.ModelAdmin):
    list_display = ("group", "kind", "email", "invited_by", "expires_at", "accepted_at")
    list_filter = ("kind", "accepted_at", "revoked_at")
    search_fields = ("email", "token", "group__name")
    readonly_fields = ("token", "created_at")


@admin.register(GroupMembership)
class GroupMembershipAdmin(admin.ModelAdmin):
    list_display = ("group", "user", "role", "joined_at")
    list_filter = ("role",)


@admin.register(GroupPlayer)
class GroupPlayerAdmin(admin.ModelAdmin):
    list_display = (
        "display_name",
        "group",
        "linked_user",
        "is_active",
        "hide_from_game_list",
    )
    list_filter = ("is_active", "hide_from_game_list", "group")
    list_editable = ("hide_from_game_list",)
    search_fields = ("display_name",)
    fields = (
        "group",
        "display_name",
        "linked_user",
        "is_active",
        "hide_from_game_list",
    )
