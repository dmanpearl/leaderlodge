from django import forms

from leaderlodge.groups.models import Group, GroupPlayer


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


class GroupInviteEmailForm(forms.Form):
    email = forms.EmailField(
        label="Email",
        widget=forms.EmailInput(
            attrs={
                "class": "form-control",
                "placeholder": "Email address",
                "autocomplete": "email",
                "id": "invite-email",
            }
        ),
    )
    player_name = forms.CharField(
        label="Player name",
        required=False,
        max_length=100,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Name",
                "id": "invite-player-name",
            }
        ),
    )

    def __init__(self, *args, group=None, **kwargs):
        self.group = group
        super().__init__(*args, **kwargs)

    def clean_email(self):
        from leaderlodge.groups.invites import user_is_member_by_email

        email = self.cleaned_data["email"].strip().lower()
        if self.group and user_is_member_by_email(self.group, email):
            raise forms.ValidationError("That email already belongs to a group member.")
        return email


class GuestInviteEmailForm(forms.Form):
    email = forms.EmailField(
        widget=forms.EmailInput(
            attrs={
                "class": "form-control form-control-sm",
                "placeholder": "Email to invite",
                "autocomplete": "email",
            }
        ),
    )

    def __init__(self, *args, group=None, **kwargs):
        self.group = group
        super().__init__(*args, **kwargs)

    def clean_email(self):
        from leaderlodge.groups.invites import user_is_member_by_email

        email = self.cleaned_data["email"].strip().lower()
        if self.group and user_is_member_by_email(self.group, email):
            raise forms.ValidationError("That email already belongs to a group member.")
        return email


class InviteAcceptForm(forms.Form):
    first_name = forms.CharField(
        label="First name",
        max_length=150,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "autocomplete": "given-name",
            }
        ),
    )


class GroupPlayerForm(forms.ModelForm):
    class Meta:
        model = GroupPlayer
        fields = ["display_name"]
        labels = {"display_name": "Guest name"}
        widgets = {
            "display_name": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Name",
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
