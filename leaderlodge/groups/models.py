from django.conf import settings
from django.db import models
from django.utils import timezone

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
    class PlayerType(models.TextChoices):
        USER = "user", "User"
        GUEST = "guest", "Guest"
        TEAM = "team", "Team"

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
    is_team = models.BooleanField(
        default=False,
        help_text="True when this roster entry is a team of member players.",
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
        override = getattr(self, "_label_override", None)
        if override is not None:
            return override
        if self.is_team:
            return self.display_name
        if self.linked_user_id:
            return format_user_display_name(self.linked_user)
        return self.display_name

    @property
    def player_type(self) -> str:
        if self.is_team:
            return self.PlayerType.TEAM
        if self.linked_user_id:
            return self.PlayerType.USER
        return self.PlayerType.GUEST

    def __str__(self) -> str:
        return f"{self.display_label} ({self.group.name})"


class GroupTeamMember(models.Model):
    team = models.ForeignKey(
        GroupPlayer,
        on_delete=models.CASCADE,
        related_name="team_members",
    )
    member = models.ForeignKey(
        GroupPlayer,
        on_delete=models.PROTECT,
        related_name="member_of_teams",
    )

    class Meta:
        unique_together = [("team", "member")]
        ordering = ["pk"]

    def __str__(self) -> str:
        return f"{self.member.display_label} in {self.team.display_name}"


class GroupInvite(models.Model):
    class Kind(models.TextChoices):
        EMAIL = "email", "Email"
        SHARE = "share", "Share link"

    group = models.ForeignKey(
        Group,
        on_delete=models.CASCADE,
        related_name="invites",
    )
    kind = models.CharField(max_length=10, choices=Kind.choices)
    email = models.EmailField(blank=True)
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="sent_group_invites",
    )
    token = models.CharField(max_length=64, unique=True)
    guest_player = models.ForeignKey(
        GroupPlayer,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="invites",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    accepted_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    accepted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="accepted_group_invites",
    )
    guest_preexisting = models.BooleanField(
        default=False,
        help_text="True when the invite targets a guest already on the roster.",
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["token"]),
            models.Index(fields=["group", "kind"]),
        ]

    def __str__(self) -> str:
        if self.kind == self.Kind.SHARE:
            return f"Share link for {self.group.name}"
        return f"Invite {self.email} to {self.group.name}"

    @property
    def is_pending(self) -> bool:
        return (
            self.accepted_at is None
            and self.revoked_at is None
            and self.expires_at > timezone.now()
        )
