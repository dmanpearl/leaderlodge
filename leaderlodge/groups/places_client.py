"""Server-side Google Places Text Search (New) client."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

SEARCH_TEXT_URL = "https://places.googleapis.com/v1/places:searchText"
FIELD_MASK = ",".join(
    [
        "places.id",
        "places.displayName",
        "places.formattedAddress",
        "places.location",
        "places.addressComponents",
    ]
)


@dataclass(frozen=True)
class PlaceHit:
    place_id: str
    display_name: str
    formatted_address: str
    lat: float
    lon: float
    city: str = ""
    state: str = ""
    country: str = ""
    postal_code: str = ""
    street_address: str = ""

    def label(self) -> str:
        if self.formatted_address:
            return f"{self.display_name}  |  {self.formatted_address}"
        if self.city and self.state:
            return f"{self.display_name}  |  {self.city}, {self.state}"
        return self.display_name


class PlacesApiError(Exception):
    """Raised when Places Text Search fails."""


def _component_text(component: dict[str, Any], *, short: bool = False) -> str:
    if short:
        return str(component.get("shortText") or component.get("longText") or "")
    return str(component.get("longText") or component.get("shortText") or "")


def extract_address_parts(
    address_components: list[dict[str, Any]] | None,
) -> dict[str, str]:
    parts = {
        "city": "",
        "state": "",
        "country": "",
        "postal_code": "",
        "street_address": "",
    }
    if not address_components:
        return parts

    route = ""
    street_number = ""
    for component in address_components:
        types = component.get("types") or []
        if "locality" in types:
            parts["city"] = _component_text(component)
        elif "administrative_area_level_1" in types:
            parts["state"] = _component_text(component, short=True)
        elif "country" in types:
            # Location.country is ISO-2 only; do not fall back to long names
            # like "Tanzania" (that overflowed varchar(2) on backfill).
            short = str(component.get("shortText") or "").strip().upper()
            parts["country"] = short if len(short) == 2 else ""
        elif "postal_code" in types:
            parts["postal_code"] = _component_text(component)
        elif "route" in types:
            route = _component_text(component)
        elif "street_number" in types:
            street_number = _component_text(component)
    parts["street_address"] = route or street_number
    return parts


def place_hit_from_api(raw: dict[str, Any]) -> PlaceHit | None:
    location = raw.get("location") or {}
    lat = location.get("latitude")
    lon = location.get("longitude")
    if lat is None or lon is None:
        return None
    try:
        lat_f = round(float(lat), 6)
        lon_f = round(float(lon), 6)
    except (TypeError, ValueError):
        return None

    display = raw.get("displayName") or {}
    if isinstance(display, dict):
        display_name = str(display.get("text") or "").strip()
    else:
        display_name = str(display).strip()
    if not display_name:
        return None

    place_id = str(raw.get("id") or "").strip()
    if not place_id:
        return None

    parts = extract_address_parts(raw.get("addressComponents"))
    return PlaceHit(
        place_id=place_id,
        display_name=display_name,
        formatted_address=str(raw.get("formattedAddress") or "").strip(),
        lat=lat_f,
        lon=lon_f,
        city=parts["city"],
        state=parts["state"],
        country=parts["country"],
        postal_code=parts["postal_code"],
        street_address=parts["street_address"],
    )


def search_places_text(
    *,
    api_key: str,
    query: str,
    max_result_count: int = 5,
    region_code: str = "us",
    timeout_seconds: float = 15.0,
) -> list[PlaceHit]:
    cleaned = query.strip()
    if not cleaned:
        raise PlacesApiError("Search query cannot be empty.")
    if not api_key.strip():
        raise PlacesApiError("Places API key is not configured.")

    body: dict[str, Any] = {
        "textQuery": cleaned,
        "maxResultCount": max(1, min(int(max_result_count), 20)),
    }
    if region_code.strip():
        body["regionCode"] = region_code.strip().lower()

    request = urllib.request.Request(
        SEARCH_TEXT_URL,
        data=json.dumps(body).encode("utf-8"),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-Goog-Api-Key": api_key.strip(),
            "X-Goog-FieldMask": FIELD_MASK,
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise PlacesApiError(f"Places API HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise PlacesApiError(f"Places API request failed: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise PlacesApiError("Places API returned invalid JSON.") from exc

    hits: list[PlaceHit] = []
    for raw in payload.get("places") or []:
        hit = place_hit_from_api(raw)
        if hit is not None:
            hits.append(hit)
    return hits
