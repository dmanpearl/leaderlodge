from django import forms

LOCATION_NAME_MAX_LENGTH = 200

LOCATION_FIELD_WIDGET_ATTRS = {
    "class": "form-control location-field-control",
    "placeholder": "Optional",
    # iOS ignores autocomplete="off" for its QuickType/autocorrect suggestions,
    # which collide with our own fuzzy autocomplete. autocorrect, autocapitalize,
    # and spellcheck turn those native suggestions off.
    "autocomplete": "off",
    "autocorrect": "off",
    "autocapitalize": "off",
    "spellcheck": "false",
    "data-location-autocomplete": "true",
}


def location_name_form_field(*, label: str = "Location") -> forms.CharField:
    return forms.CharField(
        required=False,
        max_length=LOCATION_NAME_MAX_LENGTH,
        label=label,
        widget=forms.TextInput(attrs=LOCATION_FIELD_WIDGET_ATTRS),
    )
