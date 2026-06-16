import re
import unicodedata

from django.contrib.auth.models import AbstractBaseUser
from django.core.exceptions import ValidationError

from leaderlodge.groups.models import Group, Location, LocationLibrary


def fold_accents(name: str) -> str:
    decomposed = unicodedata.normalize("NFD", name)
    return "".join(
        char for char in decomposed if unicodedata.category(char) != "Mn"
    )


def normalize_location_name(name: str) -> str:
    folded = fold_accents(name.strip().lower())
    return re.sub(r"\s+", " ", folded)


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

    location, created = Location.objects.get_or_create(
        library=library,
        normalized_name=normalized,
        defaults={"name": cleaned},
    )
    if not created and location.name != cleaned:
        location.name = cleaned
        location.save(update_fields=["name"])
    return location


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
