from django.contrib.auth.models import User
from django.db import models
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    ui_settings = models.JSONField(
        default=dict,
        blank=True,
        help_text=(
            "Per-user UI preferences, keyed by namespace slug. "
            "Insights rate limits: namespace 'insights_limits' with keys "
            "hourly, daily, unlimited (bool), global_daily, and models "
            '(e.g. {"models": {"gpt-4o-mini": {"daily": 10}}}).'
        ),
    )
    email_verified_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the user confirmed ownership of their email address.",
    )
    verification_email_sent_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When we last sent a verification link to the user's email.",
    )

    class Meta:
        verbose_name = "User Profile"

    def __str__(self):
        return f"Profile: {self.user.username}"

    @property
    def email_verified(self) -> bool:
        return self.email_verified_at is not None


class AuthEvent(models.Model):
    """Durable auth-event-log row: signups, invites, password and login events."""

    class EventType(models.TextChoices):
        SIGNUP = "signup", "Signup"
        SIGNUP_BLOCKED = "signup_blocked", "Signup blocked (bot)"
        SIGNUP_FAILED = "signup_failed", "Signup failed (validation)"
        LOGIN_FAILED = "login_failed", "Login failed"
        PASSWORD_RESET_REQUESTED = (
            "password_reset_requested",
            "Password reset requested",
        )
        PASSWORD_RESET_COMPLETED = (
            "password_reset_completed",
            "Password reset completed",
        )
        PASSWORD_CHANGED = "password_changed", "Password changed"
        INVITE_SENT = "invite_sent", "Invite sent"
        INVITE_ACCEPTED = "invite_accepted", "Invite accepted"
        EMAIL_VERIFIED = "email_verified", "Email verified"
        USER_ACTIVATED = "user_activated", "User activated"
        USER_DEACTIVATED = "user_deactivated", "User deactivated"

    class Outcome(models.TextChoices):
        SUCCESS = "success", "Success"
        BLOCKED = "blocked", "Blocked"
        FAILURE = "failure", "Failure"

    created_at = models.DateTimeField(auto_now_add=True)
    event_type = models.CharField(max_length=40, choices=EventType.choices)
    outcome = models.CharField(
        max_length=16,
        choices=Outcome.choices,
        default=Outcome.SUCCESS,
    )
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="auth_events",
    )
    email = models.CharField(
        max_length=254,
        blank=True,
        default="",
        help_text="Email attempted or affected, kept even when no user exists.",
    )
    ip_address = models.CharField(max_length=64, blank=True, default="")
    geo_city = models.CharField(max_length=100, blank=True, default="")
    geo_region = models.CharField(max_length=100, blank=True, default="")
    geo_country = models.CharField(max_length=100, blank=True, default="")
    user_agent = models.CharField(max_length=400, blank=True, default="")
    source = models.CharField(
        max_length=40,
        blank=True,
        default="",
        help_text="Where the event originated (signup, invite_join, login, admin).",
    )
    reason = models.CharField(
        max_length=80,
        blank=True,
        default="",
        help_text="Machine reason code (honeypot_filled, bad_credentials, etc.).",
    )
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
        indexes = [
            models.Index(fields=["event_type", "created_at"]),
            models.Index(fields=["outcome", "created_at"]),
            models.Index(fields=["user", "created_at"]),
            models.Index(fields=["ip_address", "created_at"]),
        ]

    def __str__(self) -> str:
        who = self.email or (self.user.username if self.user else "(unknown)")
        return f"{self.get_event_type_display()}: {who}"

    @property
    def geo_label(self) -> str:
        from leaderlodge.core.geoip import format_geo_label

        return format_geo_label(self.geo_city, self.geo_region, self.geo_country)


@receiver(post_save, sender=User)
def _create_or_update_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)
    else:
        UserProfile.objects.get_or_create(user=instance)


@receiver(pre_save, sender=User)
def _clear_email_verification_on_email_change(sender, instance, **kwargs):
    if not instance.pk:
        return
    previous_email = (
        User.objects.filter(pk=instance.pk).values_list("email", flat=True).first()
    )
    if previous_email is not None and previous_email != instance.email:
        UserProfile.objects.filter(user_id=instance.pk).update(
            email_verified_at=None,
            verification_email_sent_at=None,
        )
