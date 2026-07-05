from django import forms

LOCATION_NAME_MAX_LENGTH = 200

LOCATION_FIELD_WIDGET_ATTRS = {
    "class": "form-control location-field-control",
    "placeholder": "Optional",
    "autocomplete": "off",
    "data-location-autocomplete": "true",
}


def location_name_form_field(*, label: str = "Location") -> forms.CharField:
    return forms.CharField(
        required=False,
        max_length=LOCATION_NAME_MAX_LENGTH,
        label=label,
        widget=forms.TextInput(attrs=LOCATION_FIELD_WIDGET_ATTRS),
    )
