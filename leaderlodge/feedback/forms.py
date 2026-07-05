from django import forms
from django.core.exceptions import ValidationError

from leaderlodge.feedback.models import Feedback
from leaderlodge.games.registry import GAME_TYPES, game_type_choices


class FeedbackForm(forms.ModelForm):
    game_type_code = forms.ChoiceField(
        required=False,
        label="Game",
        choices=[],
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    class Meta:
        model = Feedback
        fields = ("feedback_type", "game_type_code", "title", "description")
        widgets = {
            "feedback_type": forms.Select(attrs={"class": "form-select"}),
            "title": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Short summary",
                    "maxlength": "200",
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 6,
                    "placeholder": "Tell us what happened or what you would like to see.",
                }
            ),
        }
        labels = {
            "feedback_type": "Type",
            "title": "Title",
            "description": "Details",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["game_type_code"].choices = [
            ("", "All games"),
            *game_type_choices(),
        ]

    def clean_game_type_code(self):
        code = self.cleaned_data.get("game_type_code", "")
        if not code:
            return ""
        if code not in GAME_TYPES:
            raise ValidationError("Choose a valid game type.")
        return code
