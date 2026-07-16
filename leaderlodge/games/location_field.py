from django import forms

from leaderlodge.groups.location_geo import LocationGeo, location_geo_from_mapping

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

LOCATION_GEO_FORM_FIELDS = (
    ("location_lat", forms.FloatField),
    ("location_lon", forms.FloatField),
    ("location_city", forms.CharField),
    ("location_state", forms.CharField),
    ("location_country", forms.CharField),
    ("location_postal_code", forms.CharField),
    ("location_street_address", forms.CharField),
    ("location_place_id", forms.CharField),
    ("location_geocode_source", forms.CharField),
)

LOCATION_GEO_FIELD_NAMES = tuple(name for name, _ in LOCATION_GEO_FORM_FIELDS)


def location_geo_post_values(data) -> dict[str, str]:
    """Carry Lookup geo fields from setup POST into the roster save form."""
    if data is None:
        return {name: "" for name in LOCATION_GEO_FIELD_NAMES}
    values = {}
    for name in LOCATION_GEO_FIELD_NAMES:
        raw = data.get(name, "")
        values[name] = "" if raw is None else str(raw)
    return values


def location_name_form_field(*, label: str = "Location") -> forms.CharField:
    return forms.CharField(
        required=False,
        max_length=LOCATION_NAME_MAX_LENGTH,
        label=label,
        widget=forms.TextInput(attrs=LOCATION_FIELD_WIDGET_ATTRS),
    )


def add_location_geo_fields(form: forms.Form) -> None:
    """Hidden geo fields posted alongside location_name from Lookup."""
    for name, field_cls in LOCATION_GEO_FORM_FIELDS:
        if field_cls is forms.FloatField:
            form.fields[name] = forms.FloatField(
                required=False,
                widget=forms.HiddenInput(
                    attrs={"data-location-geo": name.removeprefix("location_")}
                ),
            )
        else:
            max_length = {
                "location_city": 100,
                "location_state": 10,
                "location_country": 2,
                "location_postal_code": 20,
                "location_street_address": 200,
                "location_place_id": 300,
                "location_geocode_source": 20,
            }.get(name, 200)
            form.fields[name] = forms.CharField(
                required=False,
                max_length=max_length,
                widget=forms.HiddenInput(
                    attrs={"data-location-geo": name.removeprefix("location_")}
                ),
            )


def location_geo_from_form(form: forms.Form) -> LocationGeo | None:
    return location_geo_from_mapping(form.cleaned_data)
