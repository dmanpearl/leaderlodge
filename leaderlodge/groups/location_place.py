"""Set place on an existing Location (explicit re-geocode)."""

from __future__ import annotations

from django.core.exceptions import ValidationError

from leaderlodge.groups.location_geo import LocationGeo, apply_location_geo
from leaderlodge.groups.locations import rename_location
from leaderlodge.groups.models import Location


def set_location_place(
    *,
    location: Location,
    geo: LocationGeo,
    place_display_name: str = "",
    adopt_place_name: bool = False,
    force: bool = False,
) -> Location:
    if not geo.has_coordinates():
        raise ValidationError("Valid coordinates are required.")

    has_coords = location.lat is not None and location.lon is not None
    if has_coords and not force:
        raise ValidationError(
            "This location already has a pin. Confirm replace to continue."
        )

    apply_location_geo(location, geo, force=True)

    if adopt_place_name:
        cleaned = place_display_name.strip()
        if cleaned and cleaned != location.name:
            rename_location(location=location, new_name=cleaned)

    return location
