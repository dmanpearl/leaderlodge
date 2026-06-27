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
            "(e.g. {\"models\": {\"gpt-4o-mini\": {\"daily\": 10}}})."
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
