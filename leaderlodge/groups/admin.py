from django.contrib import admin

from leaderlodge.groups.models import (
    Group,
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
    list_display = ("name", "location_library", "created_by", "created_at")
    search_fields = ("name", "description")
    list_filter = ("location_library",)
    inlines = [GroupMembershipInline, GroupPlayerInline]


@admin.register(GroupMembership)
class GroupMembershipAdmin(admin.ModelAdmin):
    list_display = ("group", "user", "role", "joined_at")
    list_filter = ("role",)


@admin.register(GroupPlayer)
class GroupPlayerAdmin(admin.ModelAdmin):
    list_display = ("display_name", "group", "linked_user", "is_active")
    list_filter = ("is_active",)
    search_fields = ("display_name",)
