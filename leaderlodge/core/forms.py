from django import forms

from leaderlodge.core.admin_notification_registry import (
    DEFAULT_NOTIFICATIONS,
    NOTIFICATION_LABELS,
)
from leaderlodge.core.admin_notifications import resolved_notifications
from leaderlodge.core.models import SiteSettings


class _SiteSettingsAdminFormBase(forms.ModelForm):
    class Meta:
        model = SiteSettings
        fields = ["notify_email"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            stored = resolved_notifications(self.instance.notifications)
            for key in NOTIFICATION_LABELS:
                self.fields[key].initial = stored.get(key, False)
        else:
            for key in NOTIFICATION_LABELS:
                self.fields[key].initial = DEFAULT_NOTIFICATIONS.get(key, True)

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.notifications = {
            key: bool(self.cleaned_data.get(key, False)) for key in NOTIFICATION_LABELS
        }
        if commit:
            instance.save()
        return instance


SiteSettingsAdminForm = type(
    "SiteSettingsAdminForm",
    (_SiteSettingsAdminFormBase,),
    {
        key: forms.BooleanField(label=label, required=False)
        for key, label in NOTIFICATION_LABELS.items()
    },
)
