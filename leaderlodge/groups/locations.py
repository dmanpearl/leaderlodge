import re
import unicodedata
from dataclasses import dataclass

from django.contrib.auth.models import AbstractBaseUser
from django.core.exceptions import ValidationError
from django.db import transaction

from leaderlodge.groups.location_geo import (
    LocationGeo,
    apply_location_geo,
    copy_geo_from_source_if_needed,
)
from leaderlodge.groups.models import Group, Location, LocationLibrary

MIN_FUZZY_MERGE_SCORE = 50
MIN_SUBSEQUENCE_MERGE_SCORE = 10
MIN_SUBSEQUENCE_QUERY_LENGTH = 4
AMBIGUITY_SCORE_GAP = 5


def fold_accents(name: str) -> str:
    decomposed = unicodedata.normalize("NFD", name)
    return "".join(char for char in decomposed if unicodedata.category(char) != "Mn")


def normalize_location_name(name: str) -> str:
    folded = fold_accents(name.strip().lower())
    return re.sub(r"\s+", " ", folded)


def location_library_admin_label(library: LocationLibrary) -> str:
    """Disambiguate location libraries in admin (duplicate names, orphans)."""
    base = library.name or f"Places #{library.pk}"
    prefetched = "groups" in getattr(library, "_prefetched_objects_cache", {})
    if prefetched:
        groups = sorted(library.groups.all(), key=lambda row: row.name.lower())
        group_count = len(groups)
    else:
        group_count = library.groups.count()
        groups = list(library.groups.order_by("name")[:3])

    username = library.created_by.get_username()
    if group_count == 0:
        return f"{base} (no group, {username}, #{library.pk})"
    if group_count == 1:
        return f"{base} ({groups[0].name}, {username})"
    names = ", ".join(group.name for group in groups[:2])
    if group_count > 2:
        names = f"{names}, +{group_count - 2} more"
    return f"{base} ({names}, #{library.pk})"


def location_admin_label(location: Location) -> str:
    """Label for admin FK dropdowns when names repeat across libraries."""
    return f"{location.name} ({location_library_admin_label(location.library)})"


def normalize_for_fuzzy_match(name: str) -> str:
    base = normalize_location_name(name)
    cleaned = re.sub(r"[^a-z0-9\s']+", "", base)
    # Spoken "Bluey's" vs stored "Blueys Mar Vista" should still match.
    return cleaned.replace("'", "")


def score_location_match(query_normalized: str, candidate_normalized: str) -> int:
    if not query_normalized:
        return -1

    if query_normalized == candidate_normalized:
        return 200

    if candidate_normalized.startswith(query_normalized):
        if len(query_normalized) < len(candidate_normalized):
            # "Preston" must not merge into an existing "Preston - Passover".
            return -1
        return 100 - (len(candidate_normalized) - len(query_normalized))

    if query_normalized.startswith(candidate_normalized):
        return 90 - (len(query_normalized) - len(candidate_normalized))

    if query_normalized in candidate_normalized:
        return 50 - (len(candidate_normalized) - len(query_normalized))

    if candidate_normalized in query_normalized:
        return 45 - (len(query_normalized) - len(candidate_normalized))

    query_index = 0
    for char in candidate_normalized:
        if (
            query_index < len(query_normalized)
            and char == query_normalized[query_index]
        ):
            query_index += 1
    if query_index == len(query_normalized):
        if len(query_normalized) < len(candidate_normalized):
            return -1
        return MIN_SUBSEQUENCE_MERGE_SCORE

    return -1


def score_location_resolve_match(
    query_normalized: str, candidate_normalized: str
) -> int:
    """Score looking up an existing place (Ask / AI entry), not merge-on-create.

    Allows short spoken names to match longer Places labels, e.g. "Zinque" to
    "Zinqué Venice, Los Angeles, CA". Merge keeps the stricter
    :func:`score_location_match` so short names are not collapsed into longer ones.
    """
    if not query_normalized:
        return -1

    if query_normalized == candidate_normalized:
        return 200

    # Leading word / prefix of the stored label (space or end after the query).
    # Flat score so "Zinque" is ambiguous across multiple "Zinque …" venues
    # instead of preferring the shorter remainder.
    if candidate_normalized.startswith(query_normalized):
        rest = candidate_normalized[len(query_normalized) :]
        if not rest or rest[0].isspace():
            return 150
        first_word = candidate_normalized.split(None, 1)[0]
        if len(query_normalized) >= 4 and first_word.startswith(query_normalized):
            return 80

    return score_location_match(query_normalized, candidate_normalized)


@dataclass(frozen=True)
class DuplicateLocationPair:
    """Unordered duplicate suggestion for the Locations merge UI."""

    left: Location
    right: Location
    score: int
    reason: str  # "place_id" | "name"

    @property
    def suggested_keeper(self) -> Location:
        """Prefer more games, then geocoded, then name."""
        left_count = int(getattr(self.left, "game_count", 0) or 0)
        right_count = int(getattr(self.right, "game_count", 0) or 0)
        if left_count != right_count:
            return self.left if left_count > right_count else self.right
        left_geo = self.left.lat is not None and self.left.lon is not None
        right_geo = self.right.lat is not None and self.right.lon is not None
        if left_geo != right_geo:
            return self.left if left_geo else self.right
        if self.left.name.lower() <= self.right.name.lower():
            return self.left
        return self.right

    @property
    def suggested_source(self) -> Location:
        keeper = self.suggested_keeper
        return self.right if keeper.pk == self.left.pk else self.left


def _pair_key(a_pk: int, b_pk: int) -> tuple[int, int]:
    return (a_pk, b_pk) if a_pk < b_pk else (b_pk, a_pk)


def _fuzzy_compare_key(name: str) -> str:
    """Fuzzy key for duplicate suggestions (collapse spaces after strip)."""
    return re.sub(r"\s+", " ", normalize_for_fuzzy_match(name)).strip()


def _is_name_extension(left: str, right: str) -> bool:
    """True when one name is only a longer form of the other (e.g. Preston...)."""
    if not left or not right or left == right:
        return False
    shorter, longer = (left, right) if len(left) < len(right) else (right, left)
    return longer.startswith(shorter)


def find_duplicate_location_pairs(
    *,
    library: LocationLibrary,
) -> list[DuplicateLocationPair]:
    """Suggest pairwise merges within a library.

    Includes same non-empty ``place_id``, plus fuzzy name pairs at or above
    ``MIN_FUZZY_MERGE_SCORE``. Skips pure name-extension pairs (short name vs
    the same name with a suffix) so Find duplicates does not nag about
    intentional variants like "Preston" vs "Preston - Passover". Does not
    auto-merge; UI must confirm via ``combine_locations``.
    """
    from django.db.models import Count

    locations = list(
        library.locations.annotate(game_count=Count("games")).order_by("name", "pk")
    )
    if len(locations) < 2:
        return []

    pairs: dict[tuple[int, int], DuplicateLocationPair] = {}

    by_place_id: dict[str, list[Location]] = {}
    for location in locations:
        place_id = (location.place_id or "").strip()
        if not place_id:
            continue
        by_place_id.setdefault(place_id, []).append(location)

    for group in by_place_id.values():
        if len(group) < 2:
            continue
        for i, left in enumerate(group):
            for right in group[i + 1 :]:
                key = _pair_key(left.pk, right.pk)
                pairs[key] = DuplicateLocationPair(
                    left=left,
                    right=right,
                    score=200,
                    reason="place_id",
                )

    for i, left in enumerate(locations):
        left_norm = _fuzzy_compare_key(left.name)
        if not left_norm:
            continue
        for right in locations[i + 1 :]:
            key = _pair_key(left.pk, right.pk)
            if key in pairs:
                continue
            right_norm = _fuzzy_compare_key(right.name)
            if not right_norm:
                continue
            if _is_name_extension(left_norm, right_norm):
                continue
            score = max(
                score_location_match(left_norm, right_norm),
                score_location_match(right_norm, left_norm),
            )
            if score < MIN_FUZZY_MERGE_SCORE:
                continue
            pairs[key] = DuplicateLocationPair(
                left=left,
                right=right,
                score=score,
                reason="name",
            )

    return sorted(
        pairs.values(),
        key=lambda pair: (
            -pair.score,
            pair.left.name.lower(),
            pair.right.name.lower(),
            pair.left.pk,
            pair.right.pk,
        ),
    )


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


def get_or_create_location(
    *,
    library: LocationLibrary,
    name: str,
    geo: LocationGeo | None = None,
) -> Location:
    cleaned = name.strip()
    normalized = normalize_location_name(cleaned)
    if not normalized:
        raise ValidationError("Location name cannot be empty.")

    if geo is not None and geo.place_id:
        by_place = Location.objects.filter(
            library=library,
            place_id=geo.place_id,
        ).first()
        if by_place is not None:
            if (
                cleaned
                and by_place.name != cleaned
                and len(cleaned) > len(by_place.name)
            ):
                candidate_normalized = normalize_location_name(cleaned)
                collision = (
                    Location.objects.filter(
                        library=library,
                        normalized_name=candidate_normalized,
                    )
                    .exclude(pk=by_place.pk)
                    .exists()
                )
                # A separate, unmerged duplicate already owns that normalized
                # name (e.g. an un-geocoded "Larry's, Venice" alongside a
                # place_id-matched "Larry's"). Keep the shorter existing name
                # rather than violating the (library, normalized_name)
                # uniqueness constraint; the two rows can be merged later via
                # Combine locations.
                if not collision:
                    by_place.name = cleaned
                    by_place.normalized_name = candidate_normalized
                    by_place.save(update_fields=["name", "normalized_name"])
            return apply_location_geo(by_place, geo)

    location = Location.objects.filter(
        library=library,
        normalized_name=normalized,
    ).first()
    if location is not None:
        if location.name != cleaned:
            location.name = cleaned
            location.save(update_fields=["name"])
        return apply_location_geo(location, geo)

    fuzzy_match = find_fuzzy_location_match(library=library, cleaned=cleaned)
    if fuzzy_match is not None:
        if len(cleaned) > len(fuzzy_match.name):
            fuzzy_match.name = cleaned
            fuzzy_match.save(update_fields=["name"])
        return apply_location_geo(fuzzy_match, geo)

    location = Location.objects.create(
        library=library,
        normalized_name=normalized,
        name=cleaned,
    )
    return apply_location_geo(location, geo)


def resolve_game_location(
    *,
    group: Group,
    location_name: str,
    geo: LocationGeo | None = None,
) -> Location | None:
    cleaned = location_name.strip()
    if not cleaned:
        return None
    library = ensure_group_location_library(group)
    return get_or_create_location(library=library, name=cleaned, geo=geo)


def location_libraries_for_user(user: AbstractBaseUser):
    """Libraries attached to any group the user belongs to."""
    return LocationLibrary.objects.filter(groups__memberships__user=user).distinct()


def location_autocomplete_payload(location: Location) -> dict:
    """JSON row for fuzzy location combobox and group locations API."""
    payload = {"name": location.name}
    if location.lat is not None and location.lon is not None:
        payload.update(
            {
                "lat": location.lat,
                "lon": location.lon,
                "city": location.city or "",
                "state": location.state or "",
                "country": location.country or "",
                "postal_code": location.postal_code or "",
                "street_address": location.street_address or "",
                "place_id": location.place_id or "",
                "geocode_source": location.geocode_source or "",
            }
        )
    return payload


def locations_for_group(group: Group):
    library = ensure_group_location_library(group)
    return library.locations.order_by("name")


def rename_location(*, location: Location, new_name: str) -> Location:
    cleaned = new_name.strip()
    normalized = normalize_location_name(cleaned)
    if not normalized:
        raise ValidationError("Location name cannot be empty.")
    collision = (
        Location.objects.filter(
            library=location.library,
            normalized_name=normalized,
        )
        .exclude(pk=location.pk)
        .first()
    )
    if collision is not None:
        raise ValidationError(
            f'"{collision.name}" already exists. Use Combine instead.'
        )
    location.name = cleaned
    location.normalized_name = normalized
    location.save(update_fields=["name", "normalized_name"])
    return location


@transaction.atomic
def combine_locations(*, keeper: Location, source: Location) -> int:
    if keeper.pk == source.pk:
        raise ValidationError("Choose two different locations to combine.")
    if keeper.library_id != source.library_id:
        raise ValidationError("Locations must belong to the same group.")
    from leaderlodge.games.models import Game

    keeper = Location.objects.select_for_update().get(pk=keeper.pk)
    source = Location.objects.select_for_update().get(pk=source.pk)
    copy_geo_from_source_if_needed(keeper=keeper, source=source)
    count = Game.objects.filter(location=source).update(location=keeper)
    source.delete()
    return count
