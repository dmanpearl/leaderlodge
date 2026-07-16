"""Copy location names, geo, and inferred combines from one group to another."""

from __future__ import annotations

from dataclasses import dataclass, field

from django.db import transaction
from django.db.models import Count

from leaderlodge.groups.location_geo import GEO_COPY_FIELDS
from leaderlodge.groups.locations import (
    combine_locations,
    find_fuzzy_location_match,
    normalize_location_name,
)
from leaderlodge.groups.models import Group, Location


@dataclass
class SyncAction:
    kind: str
    detail: str


@dataclass
class SyncSummary:
    source_group: str
    dest_group: str
    dry_run: bool
    actions: list[SyncAction] = field(default_factory=list)
    skipped_src: list[str] = field(default_factory=list)
    unmatched_dst: list[str] = field(default_factory=list)
    ambiguous: list[str] = field(default_factory=list)

    @property
    def updated(self) -> int:
        return sum(1 for a in self.actions if a.kind == "update")

    @property
    def combined(self) -> int:
        return sum(1 for a in self.actions if a.kind == "combine")


def resolve_group_by_name(name: str) -> Group:
    cleaned = name.strip()
    matches = list(Group.objects.filter(name__iexact=cleaned))
    if not matches:
        raise ValueError(f"No group named {cleaned!r}.")
    if len(matches) > 1:
        labels = ", ".join(f"{g.name!r} (pk={g.pk})" for g in matches)
        raise ValueError(f"Ambiguous group name {cleaned!r}: {labels}.")
    return matches[0]


def _pick_keeper(*, src: Location, candidates: list[Location]) -> Location:
    """Prefer exact name, then place_id, then most games, then lowest pk."""
    scored: list[tuple[tuple, Location]] = []
    for loc in candidates:
        exact_name = 1 if loc.normalized_name == src.normalized_name else 0
        place_match = (
            1 if src.place_id and loc.place_id and loc.place_id == src.place_id else 0
        )
        game_count = getattr(loc, "game_count", 0) or 0
        scored.append(((-exact_name, -place_match, -game_count, loc.pk), loc))
    scored.sort(key=lambda item: item[0])
    return scored[0][1]


def _force_copy_state(*, source: Location, target: Location) -> list[str]:
    """Overwrite name and geo on target from source. Return changed field names."""
    changed: list[str] = []
    if target.name != source.name:
        target.name = source.name
        changed.append("name")
    src_norm = normalize_location_name(source.name)
    if target.normalized_name != src_norm:
        target.normalized_name = src_norm
        changed.append("normalized_name")
    for field_name in GEO_COPY_FIELDS:
        new_val = getattr(source, field_name)
        if getattr(target, field_name) != new_val:
            setattr(target, field_name, new_val)
            changed.append(field_name)
    if changed:
        target.save(update_fields=changed)
    return changed


def _match_dst_to_src(
    *,
    src_library,
    src_locations: list[Location],
    dst_locations: list[Location],
) -> tuple[dict[int, list[Location]], list[str], list[Location]]:
    """Return (src_pk -> dst matches), ambiguous notes, unmatched dst rows."""
    src_by_place = {loc.place_id: loc for loc in src_locations if loc.place_id.strip()}
    src_by_norm = {loc.normalized_name: loc for loc in src_locations}

    assigned: dict[int, Location] = {}
    ambiguous: list[str] = []

    for dst in dst_locations:
        candidates: list[Location] = []
        if dst.place_id.strip() and dst.place_id in src_by_place:
            candidates.append(src_by_place[dst.place_id])
        if dst.normalized_name in src_by_norm:
            exact = src_by_norm[dst.normalized_name]
            if exact not in candidates:
                candidates.append(exact)
        if not candidates:
            fuzzy = find_fuzzy_location_match(library=src_library, cleaned=dst.name)
            if fuzzy is not None:
                candidates.append(fuzzy)

        if not candidates:
            continue
        if len(candidates) > 1:
            # Prefer place_id, then exact name.
            if dst.place_id.strip() and dst.place_id in src_by_place:
                assigned[dst.pk] = src_by_place[dst.place_id]
            elif dst.normalized_name in src_by_norm:
                assigned[dst.pk] = src_by_norm[dst.normalized_name]
            else:
                labels = ", ".join(sorted(c.name for c in candidates))
                ambiguous.append(
                    f"dst {dst.name!r} matched multiple src locations: {labels}"
                )
            continue
        assigned[dst.pk] = candidates[0]

    by_src: dict[int, list[Location]] = {}
    for dst in dst_locations:
        src = assigned.get(dst.pk)
        if src is None:
            continue
        by_src.setdefault(src.pk, []).append(dst)

    unmatched = [dst for dst in dst_locations if dst.pk not in assigned]
    return by_src, ambiguous, unmatched


@transaction.atomic
def sync_group_locations(
    *,
    source_group: Group,
    dest_group: Group,
    dry_run: bool = False,
) -> SyncSummary:
    if source_group.pk == dest_group.pk:
        raise ValueError("Source and destination groups must be different.")
    if not source_group.location_library_id:
        raise ValueError(f"Group {source_group.name!r} has no location library.")
    if not dest_group.location_library_id:
        raise ValueError(f"Group {dest_group.name!r} has no location library.")
    if source_group.location_library_id == dest_group.location_library_id:
        raise ValueError(
            "Source and destination groups share a location library; "
            "refusing to sync."
        )

    summary = SyncSummary(
        source_group=source_group.name,
        dest_group=dest_group.name,
        dry_run=dry_run,
    )

    src_locations = list(source_group.location_library.locations.all())
    dst_locations = list(
        dest_group.location_library.locations.annotate(game_count=Count("games")).all()
    )

    by_src, ambiguous, unmatched_dst = _match_dst_to_src(
        src_library=source_group.location_library,
        src_locations=src_locations,
        dst_locations=dst_locations,
    )
    summary.ambiguous.extend(ambiguous)
    summary.unmatched_dst.extend(sorted(loc.name for loc in unmatched_dst))

    matched_src_pks = set(by_src)
    for src in src_locations:
        if src.pk not in matched_src_pks:
            summary.skipped_src.append(src.name)

    for src in src_locations:
        candidates = by_src.get(src.pk)
        if not candidates:
            continue

        keeper = _pick_keeper(src=src, candidates=candidates)
        extras = [loc for loc in candidates if loc.pk != keeper.pk]

        for extra in extras:
            detail = (
                f"combine dst {extra.name!r} into {keeper.name!r} "
                f"(aligned to src {src.name!r})"
            )
            summary.actions.append(SyncAction(kind="combine", detail=detail))
            if not dry_run:
                combine_locations(keeper=keeper, source=extra)
                keeper.refresh_from_db()

        # Re-load keeper after combines so field compares are current.
        if not dry_run:
            keeper = Location.objects.get(pk=keeper.pk)

        name_diff = keeper.name != src.name
        geo_diff = any(
            getattr(keeper, field_name) != getattr(src, field_name)
            for field_name in GEO_COPY_FIELDS
        )
        if name_diff or geo_diff:
            parts = []
            if name_diff:
                parts.append(f"name {keeper.name!r} -> {src.name!r}")
            if geo_diff:
                has_src_coords = src.lat is not None and src.lon is not None
                parts.append(
                    "geo overwrite"
                    if has_src_coords
                    else "geo fields (src has no coords)"
                )
            detail = f"update dst pk={keeper.pk}: " + "; ".join(parts)
            summary.actions.append(SyncAction(kind="update", detail=detail))
            if not dry_run:
                _force_copy_state(source=src, target=keeper)

    if dry_run:
        transaction.set_rollback(True)

    return summary
