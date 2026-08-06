"""Known venues for demo seed spreadsheets with fixed map coordinates.

Names must match the ``Where`` column in bundled Raw Games seeds. Import and
``setup_demo`` apply these coordinates so games appear on the Map without a
Places API call.
"""

from __future__ import annotations

from leaderlodge.groups.demo_seed_venues_data import DEMO_SEED_VENUES
from leaderlodge.groups.location_geo import (
    GEOCODE_SOURCE_MANUAL,
    LocationGeo,
    location_geo,
)


def demo_seed_location_names() -> tuple[str, ...]:
    return tuple(row[0] for row in DEMO_SEED_VENUES)


def geo_for_seed_location(name: str) -> LocationGeo | None:
    cleaned = (name or "").strip()
    if not cleaned:
        return None
    for venue_name, lat, lon, city, state, country in DEMO_SEED_VENUES:
        if venue_name == cleaned:
            return location_geo(
                lat=lat,
                lon=lon,
                city=city,
                state=state,
                country=country,
                geocode_source=GEOCODE_SOURCE_MANUAL,
                geocode_confidence="high",
            )
    return None
