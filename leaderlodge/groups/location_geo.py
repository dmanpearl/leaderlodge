"""Geo payload helpers for Location create/update."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.utils import timezone

from leaderlodge.groups.models import Location

GEOCODE_SOURCE_GPS = "gps"
GEOCODE_SOURCE_PLACES_LOOKUP = "places_lookup"
GEOCODE_SOURCE_MAP_PIN = "map_pin"
GEOCODE_SOURCE_TEXT_SEARCH = "text_search"
GEOCODE_SOURCE_BACKFILL_AUTO = "backfill_auto"
GEOCODE_SOURCE_BACKFILL_CONFIRMED = "backfill_confirmed"
GEOCODE_SOURCE_MANUAL = "manual"

VALID_GEOCODE_SOURCES = frozenset(
    {
        GEOCODE_SOURCE_GPS,
        GEOCODE_SOURCE_PLACES_LOOKUP,
        GEOCODE_SOURCE_MAP_PIN,
        GEOCODE_SOURCE_TEXT_SEARCH,
        GEOCODE_SOURCE_BACKFILL_AUTO,
        GEOCODE_SOURCE_BACKFILL_CONFIRMED,
        GEOCODE_SOURCE_MANUAL,
    }
)

GEO_COPY_FIELDS = (
    "lat",
    "lon",
    "city",
    "state",
    "country",
    "postal_code",
    "street_address",
    "place_id",
    "geocode_source",
    "geocode_confidence",
    "geocode_at",
)


@dataclass(frozen=True)
class LocationGeo:
    lat: float | None = None
    lon: float | None = None
    city: str = ""
    state: str = ""
    country: str = ""
    postal_code: str = ""
    street_address: str = ""
    place_id: str = ""
    geocode_source: str = ""
    geocode_confidence: str = ""

    def has_coordinates(self) -> bool:
        return self.lat is not None and self.lon is not None


def round_coord(value: float) -> float:
    return round(float(value), 6)


def location_geo_from_mapping(data: dict[str, Any] | None) -> LocationGeo | None:
    """Build LocationGeo from cleaned form data or a plain mapping."""
    if not data:
        return None

    lat_raw = data.get("location_lat", data.get("lat"))
    lon_raw = data.get("location_lon", data.get("lon"))
    if lat_raw in (None, "") or lon_raw in (None, ""):
        return None

    try:
        lat = round_coord(float(lat_raw))
        lon = round_coord(float(lon_raw))
    except (TypeError, ValueError):
        return None

    if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
        return None

    source = str(
        data.get("location_geocode_source", data.get("geocode_source", "")) or ""
    ).strip()
    if source and source not in VALID_GEOCODE_SOURCES:
        source = ""

    def _text(key_form: str, key_short: str, max_len: int) -> str:
        value = data.get(key_form, data.get(key_short, ""))
        if value is None:
            return ""
        return str(value).strip()[:max_len]

    return LocationGeo(
        lat=lat,
        lon=lon,
        city=_text("location_city", "city", 100),
        state=_text("location_state", "state", 10),
        country=_text("location_country", "country", 2).upper(),
        postal_code=_text("location_postal_code", "postal_code", 20),
        street_address=_text("location_street_address", "street_address", 200),
        place_id=_text("location_place_id", "place_id", 300),
        geocode_source=source,
        geocode_confidence=_text(
            "location_geocode_confidence", "geocode_confidence", 10
        ),
    )


def apply_location_geo(
    location: Location,
    geo: LocationGeo | None,
    *,
    force: bool = False,
) -> Location:
    """Write geo onto location when allowed by fill-in rules."""
    if geo is None or not geo.has_coordinates():
        return location
    if location.lat is not None and location.lon is not None and not force:
        return location

    location.lat = geo.lat
    location.lon = geo.lon
    location.city = geo.city
    location.state = geo.state
    location.country = geo.country
    location.postal_code = geo.postal_code
    location.street_address = geo.street_address
    location.place_id = geo.place_id
    location.geocode_source = geo.geocode_source
    location.geocode_confidence = geo.geocode_confidence
    location.geocode_at = timezone.now()
    location.save(
        update_fields=[
            "lat",
            "lon",
            "city",
            "state",
            "country",
            "postal_code",
            "street_address",
            "place_id",
            "geocode_source",
            "geocode_confidence",
            "geocode_at",
        ]
    )
    return location


def copy_geo_from_source_if_needed(*, keeper: Location, source: Location) -> None:
    """On combine: if keeper lacks coords and source has them, copy source geo."""
    if keeper.lat is not None and keeper.lon is not None:
        return
    if source.lat is None or source.lon is None:
        return
    for field in GEO_COPY_FIELDS:
        setattr(keeper, field, getattr(source, field))
    keeper.save(update_fields=list(GEO_COPY_FIELDS))
