from django import forms
from django.contrib.auth import get_user_model

from leaderlodge.groups.models import Group, GroupMembership, GroupPlayer
from leaderlodge.groups.names import format_user_display_name

User = get_user_model()


class UserMemberChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        label = format_user_display_name(obj)
        username = obj.get_username()
        if label != username:
            return f"{username} ({label})"
        return username


class GroupForm(forms.ModelForm):
    class Meta:
        model = Group
        fields = ["name", "description"]
        widgets = {
            "name": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Group name"}
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": "Optional description",
                }
            ),
        }


class GroupPlayerForm(forms.ModelForm):
    class Meta:
        model = GroupPlayer
        fields = ["display_name"]
        labels = {"display_name": "Guest name"}
        widgets = {
            "display_name": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Guest name",
                }
            ),
        }

    def __init__(self, *args, group=None, **kwargs):
        self.group = group
        super().__init__(*args, **kwargs)

    def clean_display_name(self):
        name = self.cleaned_data["display_name"].strip()
        if not name:
            raise forms.ValidationError("Name is required.")
        if (
            self.group
            and GroupPlayer.objects.filter(group=self.group, display_name=name).exists()
        ):
            raise forms.ValidationError("That name is already on the roster.")
        return name


class GroupMemberForm(forms.Form):
    # TODO: Replace listing all users with a secure, private, scalable invite
    # method (e.g. email invite link), not a public account picker.
    user = UserMemberChoiceField(
        queryset=User.objects.none(),
        label="User account",
        empty_label="Choose a user…",
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    def __init__(self, *args, group=None, **kwargs):
        self.group = group
        super().__init__(*args, **kwargs)
        if group is not None:
            member_ids = group.memberships.values_list("user_id", flat=True)
            self.fields["user"].queryset = User.objects.exclude(
                pk__in=member_ids
            ).order_by("username")

    def clean_user(self):
        user = self.cleaned_data["user"]
        if (
            self.group
            and GroupMembership.objects.filter(group=self.group, user=user).exists()
        ):
            raise forms.ValidationError("That user is already a member.")
        return user
