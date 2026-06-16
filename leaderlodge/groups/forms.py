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


class GroupPlayerForm(forms.ModelForm):
    class Meta:
        model = GroupPlayer
        fields = ["display_name"]
        labels = {"display_name": "Name"}
        widgets = {
            "display_name": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Player name",
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
