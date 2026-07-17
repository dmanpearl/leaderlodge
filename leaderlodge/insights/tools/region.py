"""Resolve city/state region filters for Ask location tools."""

from __future__ import annotations

from dataclasses import dataclass

from leaderlodge.groups.locations import locations_for_group
from leaderlodge.groups.models import Group, Location

# Stored Location.state values from Places are typically USPS abbreviations.
_US_STATE_BY_NAME: dict[str, str] = {
    "alabama": "AL",
    "alaska": "AK",
    "arizona": "AZ",
    "arkansas": "AR",
    "california": "CA",
    "colorado": "CO",
    "connecticut": "CT",
    "delaware": "DE",
    "district of columbia": "DC",
    "florida": "FL",
    "georgia": "GA",
    "hawaii": "HI",
    "idaho": "ID",
    "illinois": "IL",
    "indiana": "IN",
    "iowa": "IA",
    "kansas": "KS",
    "kentucky": "KY",
    "louisiana": "LA",
    "maine": "ME",
    "maryland": "MD",
    "massachusetts": "MA",
    "michigan": "MI",
    "minnesota": "MN",
    "mississippi": "MS",
    "missouri": "MO",
    "montana": "MT",
    "nebraska": "NE",
    "nevada": "NV",
    "new hampshire": "NH",
    "new jersey": "NJ",
    "new mexico": "NM",
    "new york": "NY",
    "north carolina": "NC",
    "north dakota": "ND",
    "ohio": "OH",
    "oklahoma": "OK",
    "oregon": "OR",
    "pennsylvania": "PA",
    "rhode island": "RI",
    "south carolina": "SC",
    "south dakota": "SD",
    "tennessee": "TN",
    "texas": "TX",
    "utah": "UT",
    "vermont": "VT",
    "virginia": "VA",
    "washington": "WA",
    "west virginia": "WV",
    "wisconsin": "WI",
    "wyoming": "WY",
}

_US_STATE_CODES = frozenset(_US_STATE_BY_NAME.values())
_US_STATE_NAME_BY_CODE = {
    code: name.title() for name, code in _US_STATE_BY_NAME.items()
}
# Fix DC title casing.
_US_STATE_NAME_BY_CODE["DC"] = "District of Columbia"


def normalize_region_state(value: str) -> str:
    """Map a user/LLM state string to the short code stored on Location.state."""
    cleaned = " ".join(value.strip().split())
    if not cleaned:
        return ""
    lower = cleaned.lower()
    if lower in _US_STATE_BY_NAME:
        return _US_STATE_BY_NAME[lower]
    upper = cleaned.upper()
    if upper in _US_STATE_CODES:
        return upper
    return cleaned


def normalize_region_city(value: str) -> str:
    return " ".join(value.strip().split())


def split_city_state_blob(city: str, state: str) -> tuple[str, str]:
    """If city looks like 'Santa Monica, CA', split when state was omitted."""
    city = normalize_region_city(city)
    state = normalize_region_city(state)
    if city and not state and "," in city:
        left, right = city.rsplit(",", 1)
        right = right.strip()
        if right and len(right) <= 20:
            return normalize_region_city(left), right
    return city, state


def state_display_label(state_code: str) -> str:
    code = normalize_region_state(state_code)
    if code in _US_STATE_NAME_BY_CODE:
        return _US_STATE_NAME_BY_CODE[code]
    return state_code


@dataclass(frozen=True)
class RegionMatch:
    city: str
    state: str
    locations: tuple[Location, ...]
    venues_in_library: int
    venues_with_city_or_state: int
    exclude: bool = False

    @property
    def location_ids(self) -> list[int]:
        return [location.pk for location in self.locations]

    @property
    def coverage_thin(self) -> bool:
        """True when few library venues have city/state filled relative to total."""
        if self.venues_in_library == 0:
            return True
        if self.venues_with_city_or_state == 0:
            return True
        return self.venues_with_city_or_state < max(3, self.venues_in_library // 2)

    def region_label(self) -> str:
        parts: list[str] = []
        if self.city:
            parts.append(self.city)
        if self.state:
            parts.append(
                state_display_label(self.state) if len(self.state) == 2 else self.state
            )
        label = ", ".join(parts) if parts else "region"
        if self.exclude:
            return f"outside {label}"
        return label

    def coverage_note(self) -> str | None:
        if not self.locations:
            return None
        if not self.coverage_thin:
            if self.exclude:
                return (
                    "Outside-region rankings only include venues with city/state "
                    "filled that do not match the excluded region. Venues with "
                    "blank city/state are omitted."
                )
            return None
        note = (
            f"Only {self.venues_with_city_or_state} of {self.venues_in_library} "
            "saved venues have city or state filled. Regional rankings only include "
            "games at matched venues with geo fields; other games are omitted."
        )
        if self.exclude:
            note += " Outside-region queries also omit venues with blank city/state."
        return note


def _location_matches_region(location: Location, *, city_q: str, state_q: str) -> bool:
    if city_q and location.city.strip().lower() != city_q.lower():
        return False
    if state_q and location.state.strip().lower() != state_q.lower():
        return False
    return True


def _exclude_region_locations(
    library: list[Location], *, city_q: str, state_q: str
) -> tuple[Location, ...]:
    """Venues with known geo that do not match the excluded city/state."""
    if state_q and not city_q:
        return tuple(
            loc
            for loc in library
            if loc.state.strip() and loc.state.strip().lower() != state_q.lower()
        )
    if city_q and not state_q:
        return tuple(
            loc
            for loc in library
            if loc.city.strip() and loc.city.strip().lower() != city_q.lower()
        )
    return tuple(
        loc
        for loc in library
        if (loc.city.strip() or loc.state.strip())
        and not _location_matches_region(loc, city_q=city_q, state_q=state_q)
    )


def resolve_region_locations(
    group: Group,
    *,
    city: str | None = None,
    state: str | None = None,
    exclude: bool = False,
) -> RegionMatch:
    city_raw = city or ""
    state_raw = state or ""
    city_q, state_q = split_city_state_blob(city_raw, state_raw)
    city_q = normalize_region_city(city_q)
    state_q = normalize_region_state(state_q)

    if not city_q and not state_q:
        raise ValueError("Provide city and/or state for a regional query.")

    library = list(locations_for_group(group))
    venues_with_geo = sum(1 for loc in library if loc.city.strip() or loc.state.strip())

    if exclude:
        matched = _exclude_region_locations(library, city_q=city_q, state_q=state_q)
    else:
        matched = tuple(
            loc
            for loc in library
            if _location_matches_region(loc, city_q=city_q, state_q=state_q)
        )

    if not matched:
        label_parts: list[str] = []
        if city_q:
            label_parts.append(f"city={city_q!r}")
        if state_q:
            label_parts.append(f"state={state_q!r}")
        scope = "outside " if exclude else ""
        raise ValueError(
            "No venues matched "
            + scope
            + " and ".join(label_parts)
            + " in this group. Regional answers need city/state on saved venues."
        )

    return RegionMatch(
        city=city_q,
        state=state_q,
        locations=matched,
        venues_in_library=len(library),
        venues_with_city_or_state=venues_with_geo,
        exclude=exclude,
    )


def region_match_payload(match: RegionMatch) -> dict:
    note = match.coverage_note()
    payload = {
        "city": match.city or None,
        "state": match.state or None,
        "exclude": match.exclude,
        "region_label": match.region_label(),
        "matched_venue_count": len(match.locations),
        "matched_venues": [
            {
                "location_id": loc.pk,
                "name": loc.name,
                "city": loc.city or None,
                "state": loc.state or None,
            }
            for loc in match.locations
        ],
        "venues_in_library": match.venues_in_library,
        "venues_with_city_or_state": match.venues_with_city_or_state,
        "coverage_thin": match.coverage_thin,
    }
    if note:
        payload["coverage_note"] = note
    return payload
