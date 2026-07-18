"""GeoJSON and filter helpers for the games map viewer."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from django.db.models import Count, Q, QuerySet

from leaderlodge.games.models import Game
from leaderlodge.games.registry import GAME_TYPES
from leaderlodge.groups.locations import GAME_CODE_SHORT
from leaderlodge.groups.models import Group, Location
from leaderlodge.groups.services import can_view_group, visible_groups


def resolve_map_group(*, user, group_id: str, groups: list[Group] | None = None):
    available = groups if groups is not None else list(visible_groups(user))
    if group_id.isdigit():
        group = next((g for g in available if g.pk == int(group_id)), None)
        if group is not None and can_view_group(user, group):
            return group
    if available:
        return available[0]
    return None


def geocoded_locations_for_group(group: Group) -> QuerySet[Location]:
    if group.location_library_id is None:
        return Location.objects.none()
    return Location.objects.filter(
        library_id=group.location_library_id,
        lat__isnull=False,
        lon__isnull=False,
    )


def group_location_counts(group: Group) -> tuple[int, int]:
    """Return (total_locations, geocoded_locations) for a group's library."""
    if group.location_library_id is None:
        return 0, 0
    total = Location.objects.filter(library_id=group.location_library_id).count()
    geocoded = geocoded_locations_for_group(group).count()
    return total, geocoded


def group_has_ungeocoded_locations(group: Group) -> bool:
    total, geocoded = group_location_counts(group)
    return total > geocoded


def map_location_name_choices(group: Group) -> list[str]:
    """Venue names for map Location type-ahead (geocoded locations with games)."""
    location_ids = (
        Game.objects.filter(
            group=group,
            location__isnull=False,
            location__lat__isnull=False,
            location__lon__isnull=False,
        )
        .values_list("location_id", flat=True)
        .distinct()
    )
    return list(
        Location.objects.filter(pk__in=location_ids)
        .order_by("name")
        .values_list("name", flat=True)
    )


def map_country_choices(group: Group) -> list[str]:
    return list(
        geocoded_locations_for_group(group)
        .exclude(country="")
        .values_list("country", flat=True)
        .distinct()
        .order_by("country")
    )


def map_state_choices(group: Group, *, country: str = "") -> list[str]:
    qs = geocoded_locations_for_group(group).exclude(state="")
    if country.strip():
        qs = qs.filter(country__iexact=country.strip())
    return list(qs.values_list("state", flat=True).distinct().order_by("state"))


def map_city_choices(group: Group, *, country: str = "", state: str = "") -> list[str]:
    qs = geocoded_locations_for_group(group).exclude(city="")
    if country.strip():
        qs = qs.filter(country__iexact=country.strip())
    if state.strip():
        qs = qs.filter(state__iexact=state.strip())
    return list(qs.values_list("city", flat=True).distinct().order_by("city"))


def map_geo_cascade_tree(group: Group) -> dict[str, dict[str, list[str]]]:
    """Country -> state -> cities for client-side filter cascading."""
    tree: dict[str, dict[str, set[str]]] = {}
    rows = (
        geocoded_locations_for_group(group)
        .exclude(country="")
        .values_list("country", "state", "city")
    )
    for country, state, city in rows:
        country_key = (country or "").strip().upper()
        state_key = (state or "").strip()
        city_key = (city or "").strip()
        if not country_key:
            continue
        states = tree.setdefault(country_key, {})
        if not state_key:
            continue
        cities = states.setdefault(state_key, set())
        if city_key:
            cities.add(city_key)
    return {
        country: {state: sorted(cities) for state, cities in sorted(states.items())}
        for country, states in sorted(tree.items())
    }


def parse_map_bbox(raw: str) -> tuple[float, float, float, float] | None:
    """Parse bbox=lon_min,lat_min,lon_max,lat_max. Returns None if invalid."""
    parts = [part.strip() for part in str(raw or "").split(",")]
    if len(parts) != 4:
        return None
    try:
        lon_min, lat_min, lon_max, lat_max = (float(part) for part in parts)
    except ValueError:
        return None
    if not (
        -180.0 <= lon_min <= 180.0
        and -180.0 <= lon_max <= 180.0
        and -90.0 <= lat_min <= 90.0
        and -90.0 <= lat_max <= 90.0
    ):
        return None
    if lon_min > lon_max or lat_min > lat_max:
        return None
    return lon_min, lat_min, lon_max, lat_max


def expand_map_bbox(
    bbox: tuple[float, float, float, float], *, pad_ratio: float = 0.15
) -> tuple[float, float, float, float]:
    lon_min, lat_min, lon_max, lat_max = bbox
    lon_pad = max((lon_max - lon_min) * pad_ratio, 0.01)
    lat_pad = max((lat_max - lat_min) * pad_ratio, 0.01)
    return (
        max(lon_min - lon_pad, -180.0),
        max(lat_min - lat_pad, -90.0),
        min(lon_max + lon_pad, 180.0),
        min(lat_max + lat_pad, 90.0),
    )


def _filtered_games_for_map(
    *,
    group: Group,
    game_type_code: str = "",
    player_id: str = "",
    period=None,
) -> QuerySet[Game]:
    from leaderlodge.leaderboards.period import (
        LeaderboardPeriod,
        filter_results_by_period,
    )

    games_qs = Game.objects.filter(group=group, location__isnull=False)
    if game_type_code in GAME_TYPES:
        games_qs = games_qs.filter(game_type_code=game_type_code)
    if player_id.isdigit():
        pid = int(player_id)
        games_qs = games_qs.filter(
            Q(participant_results__player_id=pid)
            | Q(participant_results__player__team_members__member_id=pid)
        ).distinct()
    if isinstance(period, LeaderboardPeriod) and period.is_filtered:
        games_qs = filter_results_by_period(games_qs, period, game_prefix="")
    return games_qs


def build_map_features(
    *,
    group: Group,
    game_type_code: str = "",
    player_id: str = "",
    period=None,
    city: str = "",
    state: str = "",
    country: str = "",
    location_name: str = "",
    bbox: tuple[float, float, float, float] | None = None,
) -> list[dict[str, Any]]:
    """Return GeoJSON Feature dicts for geocoded venues matching filters."""
    games_qs = _filtered_games_for_map(
        group=group,
        game_type_code=game_type_code,
        player_id=player_id,
        period=period,
    ).filter(location__lat__isnull=False, location__lon__isnull=False)

    city = city.strip()
    state = state.strip()
    country = country.strip().upper()
    location_name = location_name.strip()

    if city:
        games_qs = games_qs.filter(location__city__icontains=city)
    if state:
        games_qs = games_qs.filter(location__state__iexact=state)
    if country:
        games_qs = games_qs.filter(location__country__iexact=country)
    if location_name:
        games_qs = games_qs.filter(location__name__icontains=location_name)
    if bbox is not None:
        lon_min, lat_min, lon_max, lat_max = bbox
        games_qs = games_qs.filter(
            location__lon__gte=lon_min,
            location__lon__lte=lon_max,
            location__lat__gte=lat_min,
            location__lat__lte=lat_max,
        )

    counts: dict[int, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    location_ids: set[int] = set()
    for row in games_qs.values("location_id", "game_type_code").annotate(n=Count("id")):
        loc_id = row["location_id"]
        if loc_id is None:
            continue
        location_ids.add(loc_id)
        counts[loc_id][row["game_type_code"]] += row["n"]

    if not location_ids:
        return []

    features: list[dict[str, Any]] = []
    locations = Location.objects.filter(pk__in=location_ids).order_by("name", "pk")
    for location in locations:
        game_counts = {
            code: n
            for code, n in sorted(counts[location.pk].items())
            if code in GAME_TYPES
        }
        total = sum(game_counts.values())
        if total <= 0:
            continue
        features.append(
            {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [float(location.lon), float(location.lat)],
                },
                "properties": {
                    "location_id": location.pk,
                    "name": location.name,
                    "city": location.city or "",
                    "state": location.state or "",
                    "country": location.country or "",
                    "game_counts": game_counts,
                    "game_count_labels": [
                        {
                            "code": code,
                            "short": GAME_CODE_SHORT.get(code, code[:2].upper()),
                            "name": GAME_TYPES[code].name,
                            "count": n,
                        }
                        for code, n in game_counts.items()
                    ],
                    "total_games": total,
                },
            }
        )
    return features


def map_geojson_collection(features: list[dict[str, Any]]) -> dict[str, Any]:
    return {"type": "FeatureCollection", "features": features}
