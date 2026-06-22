from django.contrib.auth.models import User
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    ui_settings = models.JSONField(
        default=dict,
        blank=True,
        help_text="Per-user UI preferences, keyed by view/feature namespace slug.",
    )

    class Meta:
        verbose_name = "User Profile"

    def __str__(self):
        return f"Profile: {self.user.username}"


@receiver(post_save, sender=User)
def _create_or_update_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)
    else:
        UserProfile.objects.get_or_create(user=instance)
