import re
import unicodedata

from django.contrib.auth.models import AbstractBaseUser
from django.core.exceptions import ValidationError

from leaderlodge.groups.models import Group, Location, LocationLibrary

MIN_FUZZY_MERGE_SCORE = 50
MIN_SUBSEQUENCE_MERGE_SCORE = 10
MIN_SUBSEQUENCE_QUERY_LENGTH = 4
AMBIGUITY_SCORE_GAP = 5


def fold_accents(name: str) -> str:
    decomposed = unicodedata.normalize("NFD", name)
    return "".join(
        char for char in decomposed if unicodedata.category(char) != "Mn"
    )


def normalize_location_name(name: str) -> str:
    folded = fold_accents(name.strip().lower())
    return re.sub(r"\s+", " ", folded)


def normalize_for_fuzzy_match(name: str) -> str:
    base = normalize_location_name(name)
    return re.sub(r"[^a-z0-9\s']+", "", base)


def score_location_match(query_normalized: str, candidate_normalized: str) -> int:
    if not query_normalized:
        return -1

    if query_normalized == candidate_normalized:
        return 200

    if candidate_normalized.startswith(query_normalized):
        return 100 - (len(candidate_normalized) - len(query_normalized))

    if query_normalized.startswith(candidate_normalized):
        return 90 - (len(query_normalized) - len(candidate_normalized))

    if query_normalized in candidate_normalized:
        return 50 - (len(candidate_normalized) - len(query_normalized))

    if candidate_normalized in query_normalized:
        return 45 - (len(query_normalized) - len(candidate_normalized))

    query_index = 0
    for char in candidate_normalized:
        if query_index < len(query_normalized) and char == query_normalized[query_index]:
            query_index += 1
    if query_index == len(query_normalized):
        return MIN_SUBSEQUENCE_MERGE_SCORE

    return -1


def find_fuzzy_location_match(
    *,
    library: LocationLibrary,
    cleaned: str,
) -> Location | None:
    query = normalize_for_fuzzy_match(cleaned)
    if not query:
        return None

    scored: list[tuple[int, Location]] = []
    for location in library.locations.all():
        score = score_location_match(
            query,
            normalize_for_fuzzy_match(location.name),
        )
        if score >= MIN_SUBSEQUENCE_MERGE_SCORE:
            scored.append((score, location))

    if not scored:
        return None

    scored.sort(key=lambda item: (-item[0], item[1].name))
    best_score, best_location = scored[0]

    if best_score >= MIN_FUZZY_MERGE_SCORE:
        if len(scored) > 1 and scored[1][0] >= best_score - AMBIGUITY_SCORE_GAP:
            return None
        return best_location

    if (
        best_score >= MIN_SUBSEQUENCE_MERGE_SCORE
        and len(query) >= MIN_SUBSEQUENCE_QUERY_LENGTH
        and (len(scored) == 1 or scored[1][0] < best_score - AMBIGUITY_SCORE_GAP)
    ):
        return best_location

    return None


def create_location_library(
    *,
    user: AbstractBaseUser,
    name: str = "",
) -> LocationLibrary:
    return LocationLibrary.objects.create(
        name=name.strip(),
        created_by=user,
    )


def ensure_group_location_library(group: Group) -> LocationLibrary:
    if group.location_library_id:
        return group.location_library

    library = create_location_library(
        user=group.created_by,
        name=f"{group.name} places",
    )
    group.location_library = library
    group.save(update_fields=["location_library"])
    return library


def get_or_create_location(*, library: LocationLibrary, name: str) -> Location:
    cleaned = name.strip()
    normalized = normalize_location_name(cleaned)
    if not normalized:
        raise ValidationError("Location name cannot be empty.")

    location = Location.objects.filter(
        library=library,
        normalized_name=normalized,
    ).first()
    if location is not None:
        if location.name != cleaned:
            location.name = cleaned
            location.save(update_fields=["name"])
        return location

    fuzzy_match = find_fuzzy_location_match(library=library, cleaned=cleaned)
    if fuzzy_match is not None:
        return fuzzy_match

    return Location.objects.create(
        library=library,
        normalized_name=normalized,
        name=cleaned,
    )


def resolve_game_location(*, group: Group, location_name: str) -> Location | None:
    cleaned = location_name.strip()
    if not cleaned:
        return None
    library = ensure_group_location_library(group)
    return get_or_create_location(library=library, name=cleaned)


def location_libraries_for_user(user: AbstractBaseUser):
    """Libraries attached to any group the user belongs to."""
    return LocationLibrary.objects.filter(groups__memberships__user=user).distinct()


def locations_for_group(group: Group):
    library = ensure_group_location_library(group)
    return library.locations.order_by("name")
