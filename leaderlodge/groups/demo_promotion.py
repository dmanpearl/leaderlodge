"""Promote games from a real group into the public Demo group.

Applies the player name remapping (`demo_promotion_names.PLAYER_NAME_MAP`)
and location remapping (`demo_promotion_locations.LOCATION_NAME_MAP`) so
Demo shows realistic, anonymized game history instead of live production
data. See those two modules for the remapping policy.

Idempotent: every promoted game is tagged with
`import_source="promote:<source group name>"` and
`import_row_key=f"game-{source_game.pk}"`, reusing the same
`(group, import_source, import_row_key)` uniqueness that the spreadsheet
seed importers rely on (see `leaderlodge.games.importing.service`).
Re-running only adds games that were not already promoted. `purge_promoted_games`
deletes everything previously promoted for a clean full redo.

Game notes and score edit history are intentionally never copied: notes are
free text that hasn't been audited for personal references, and edit history
snapshots would carry real names/scores forward. Only the current
participant results of each game are promoted.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from django.contrib.auth.models import AbstractBaseUser
from django.db import transaction

from leaderlodge.games.models import Game
from leaderlodge.games.services import ParticipantInput, record_game
from leaderlodge.groups.demo_promotion_locations import LOCATION_NAME_MAP
from leaderlodge.groups.demo_promotion_names import PLAYER_NAME_MAP
from leaderlodge.groups.location_geo import LocationGeo, location_geo
from leaderlodge.groups.locations import resolve_game_location
from leaderlodge.groups.models import Group, GroupPlayer, Location
from leaderlodge.groups.teams import resolve_side_player

PROMOTION_SOURCE_PREFIX = "promote"

# Round blurred coordinates to this many decimal places (about half a mile to
# a mile of imprecision), matching the policy documented in
# demo_promotion_locations.py.
GEO_BLUR_DECIMALS = 2


def promotion_import_source(source_group_name: str) -> str:
    return f"{PROMOTION_SOURCE_PREFIX}:{source_group_name}"


def promotion_row_key(source_game_pk: int) -> str:
    return f"game-{source_game_pk}"


class UnmappedPlayerError(Exception):
    """Raised when a source player has no entry in PLAYER_NAME_MAP."""

    def __init__(self, display_label: str):
        self.display_label = display_label
        super().__init__(f"No demo name mapping for player {display_label!r}.")


@dataclass
class PromotionSummary:
    game_type_code: str | None = None
    total_source_games: int = 0
    created: int = 0
    already_promoted: int = 0
    skipped_unmapped_player: int = 0
    unmapped_player_names: set[str] = field(default_factory=set)


def _blur_coord(value: float) -> float:
    return round(float(value), GEO_BLUR_DECIMALS)


def _resolve_dest_location_geo(
    *, source_location: Location, is_remapped: bool
) -> LocationGeo | None:
    if source_location.lat is None or source_location.lon is None:
        return None
    if is_remapped:
        # Personal location: keep the pin in roughly the right area without
        # preserving enough precision to reverse-geocode an exact address.
        return location_geo(
            lat=_blur_coord(source_location.lat),
            lon=_blur_coord(source_location.lon),
        )
    return location_geo(
        lat=source_location.lat,
        lon=source_location.lon,
        city=source_location.city,
        state=source_location.state,
        country=source_location.country,
        postal_code=source_location.postal_code,
        street_address=source_location.street_address,
        place_id=source_location.place_id,
        geocode_source=source_location.geocode_source,
        geocode_confidence=source_location.geocode_confidence,
    )


def _resolve_dest_location(
    *, dest_group: Group, source_location: Location | None
) -> Location | None:
    if source_location is None:
        return None
    dest_name = LOCATION_NAME_MAP.get(source_location.name, source_location.name)
    is_remapped = dest_name != source_location.name
    geo = _resolve_dest_location_geo(
        source_location=source_location, is_remapped=is_remapped
    )
    return resolve_game_location(group=dest_group, location_name=dest_name, geo=geo)


def _resolve_dest_player(
    *,
    dest_group: Group,
    source_player: GroupPlayer,
    dest_player_cache: dict[int, GroupPlayer],
) -> GroupPlayer:
    if source_player.pk in dest_player_cache:
        return dest_player_cache[source_player.pk]

    if source_player.is_team:
        members = [
            _resolve_dest_player(
                dest_group=dest_group,
                source_player=link.member,
                dest_player_cache=dest_player_cache,
            )
            for link in source_player.team_members.select_related("member").order_by(
                "pk"
            )
        ]
        dest_player = resolve_side_player(group=dest_group, members=members)
    else:
        mapped_name = PLAYER_NAME_MAP.get(source_player.display_label)
        if mapped_name is None:
            raise UnmappedPlayerError(source_player.display_label)
        dest_player, _created = GroupPlayer.objects.get_or_create(
            group=dest_group,
            display_name=mapped_name,
        )

    dest_player_cache[source_player.pk] = dest_player
    return dest_player


@transaction.atomic
def promote_games(
    *,
    source_group: Group,
    dest_group: Group,
    recorded_by: AbstractBaseUser,
    game_type_code: str | None = None,
    dry_run: bool = False,
) -> PromotionSummary:
    """Copy games from source_group into dest_group with name/location remapping.

    Wrapped in a single transaction so a dry run can exercise the exact same
    player/location find-or-create paths (to accurately preview what would be
    created) and then roll everything back before returning.
    """
    summary = PromotionSummary(game_type_code=game_type_code)
    import_source = promotion_import_source(source_group.name)

    already_promoted_keys = set(
        Game.objects.filter(
            group=dest_group,
            import_source=import_source,
        ).values_list("import_row_key", flat=True)
    )

    source_games = (
        Game.objects.filter(group=source_group)
        .select_related("location")
        .prefetch_related("participant_results__player__team_members__member")
        .order_by("pk")
    )
    if game_type_code:
        source_games = source_games.filter(game_type_code=game_type_code)

    dest_player_cache: dict[int, GroupPlayer] = {}
    dest_location_cache: dict[int, Location | None] = {}

    for source_game in source_games:
        summary.total_source_games += 1
        row_key = promotion_row_key(source_game.pk)
        if row_key in already_promoted_keys:
            summary.already_promoted += 1
            continue

        try:
            participants = [
                ParticipantInput(
                    player=_resolve_dest_player(
                        dest_group=dest_group,
                        source_player=result.player,
                        dest_player_cache=dest_player_cache,
                    ),
                    score=result.score,
                    result=result.result,
                    placement=result.placement,
                )
                for result in source_game.participant_results.all()
            ]
        except UnmappedPlayerError as exc:
            summary.skipped_unmapped_player += 1
            summary.unmapped_player_names.add(exc.display_label)
            continue

        if source_game.location_id not in dest_location_cache:
            dest_location_cache[source_game.location_id] = _resolve_dest_location(
                dest_group=dest_group,
                source_location=source_game.location,
            )
        dest_location = dest_location_cache[source_game.location_id]

        if dry_run:
            summary.created += 1
            continue

        record_game(
            user=recorded_by,
            group=dest_group,
            game_type_code=source_game.game_type_code,
            played_on=source_game.played_on,
            participants=participants,
            location=dest_location,
            import_source=import_source,
            import_row_key=row_key,
            half_weight=source_game.half_weight,
            score_type=source_game.score_type,
        )
        summary.created += 1
        already_promoted_keys.add(row_key)

    if dry_run:
        transaction.set_rollback(True)

    return summary


def purge_promoted_games(*, source_group: Group, dest_group: Group) -> int:
    """Delete every game previously promoted from source_group into dest_group."""
    queryset = Game.objects.filter(
        group=dest_group,
        import_source=promotion_import_source(source_group.name),
    )
    count = queryset.count()
    queryset.delete()
    return count
