from django.conf import settings
from django.db import models

from leaderlodge.groups.names import format_user_display_name


class LocationLibrary(models.Model):
    name = models.CharField(max_length=100, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="location_libraries",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "location libraries"
        ordering = ["name", "pk"]

    def __str__(self) -> str:
        return self.name or f"Places #{self.pk}"


class Location(models.Model):
    library = models.ForeignKey(
        LocationLibrary,
        on_delete=models.CASCADE,
        related_name="locations",
    )
    name = models.CharField(max_length=200)
    normalized_name = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("library", "normalized_name")]
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Group(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_groups",
    )
    is_demo = models.BooleanField(
        default=False,
        help_text="When enabled, anyone can view this group read-only (demo/sample data).",
    )
    location_library = models.ForeignKey(
        LocationLibrary,
        on_delete=models.PROTECT,
        related_name="groups",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class GroupMembership(models.Model):
    class Role(models.TextChoices):
        OWNER = "owner", "Owner"
        EDITOR = "editor", "Editor"
        MEMBER = "member", "Member"

    group = models.ForeignKey(
        Group,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="group_memberships",
    )
    role = models.CharField(
        max_length=10,
        choices=Role.choices,
        default=Role.MEMBER,
        help_text="Owner and Editor can manage members; Member is view and play only.",
    )
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("group", "user")]

    def __str__(self) -> str:
        return f"{self.user} in {self.group}"


class GroupPlayer(models.Model):
    group = models.ForeignKey(
        Group,
        on_delete=models.CASCADE,
        related_name="players",
    )
    display_name = models.CharField(max_length=100)
    linked_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="group_player_profiles",
    )
    is_active = models.BooleanField(default=True)
    hide_from_game_list = models.BooleanField(
        default=False,
        verbose_name="Hide from game stats",
        help_text="Omit this player from the game list stats table.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("group", "display_name")]
        ordering = ["display_name"]

    @property
    def display_label(self) -> str:
        if self.linked_user_id:
            return format_user_display_name(self.linked_user)
        return self.display_name

    def __str__(self) -> str:
        return f"{self.display_label} ({self.group.name})"
