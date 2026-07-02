from __future__ import annotations

from leaderlodge.groups.locations import (
    AMBIGUITY_SCORE_GAP,
    ensure_group_location_library,
    find_fuzzy_location_match,
    locations_for_group,
    normalize_for_fuzzy_match,
    score_location_match,
)
from leaderlodge.groups.models import Group, Location


def resolve_location_query(group: Group, query: str) -> Location:
    cleaned = query.strip()
    if not cleaned:
        raise ValueError("A location name query is required.")

    lowered = cleaned.lower()
    exact_matches = [
        location
        for location in locations_for_group(group)
        if location.name.lower() == lowered
    ]
    if len(exact_matches) == 1:
        return exact_matches[0]
    if len(exact_matches) > 1:
        labels = ", ".join(sorted(location.name for location in exact_matches))
        raise ValueError(f"Ambiguous location {query!r}. Matches: {labels}.")

    library = ensure_group_location_library(group)
    fuzzy_match = find_fuzzy_location_match(library=library, cleaned=cleaned)
    if fuzzy_match is not None:
        return fuzzy_match

    query_normalized = normalize_for_fuzzy_match(cleaned)
    scored: list[tuple[int, Location]] = []
    for location in locations_for_group(group):
        score = score_location_match(
            query_normalized,
            normalize_for_fuzzy_match(location.name),
        )
        if score >= 0:
            scored.append((score, location))
    if not scored:
        raise ValueError(f"No location matched {query!r} in this group.")

    scored.sort(key=lambda item: (-item[0], item[1].name.lower()))
    best_score, best_location = scored[0]
    if len(scored) > 1 and scored[1][0] >= best_score - AMBIGUITY_SCORE_GAP:
        labels = ", ".join(
            sorted(location.name for _, location in scored[:3] if _ >= best_score - 1)
        )
        raise ValueError(f"Ambiguous location {query!r}. Matches: {labels}.")
    return best_location


def resolve_location_for_group(
    group: Group,
    *,
    location_id: int | None = None,
    location_query: str | None = None,
) -> Location:
    if location_id is not None and location_query:
        raise ValueError("Provide location_id or location_query, not both.")

    if location_query:
        return resolve_location_query(group, location_query)

    if location_id is None:
        raise ValueError("location_id or location_query is required.")

    library = ensure_group_location_library(group)
    location = library.locations.filter(pk=location_id).first()
    if location is None:
        raise ValueError(f"location_id {location_id} not found in this group.")
    return location
