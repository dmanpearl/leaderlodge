from django.contrib import admin

from leaderlodge.groups.models import Group, GroupMembership, GroupPlayer


class GroupMembershipInline(admin.TabularInline):
    model = GroupMembership
    extra = 0


class GroupPlayerInline(admin.TabularInline):
    model = GroupPlayer
    extra = 0


@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = ("name", "created_by", "created_at")
    search_fields = ("name", "description")
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
