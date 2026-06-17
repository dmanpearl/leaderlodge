from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from django.contrib.auth.models import AbstractBaseUser
from django.db import transaction

from leaderlodge.games.importing.progressiverummy import (
    ProgressiveRummyRow,
    parse_progressiverummy_workbook,
)
from leaderlodge.games.importing.scorekeeper import ScoreKeeperRow, parse_scorekeeper_workbook
from leaderlodge.games.models import Game
from leaderlodge.games.registry import get_game_type
from leaderlodge.games.scoring import assign_results_from_scores
from leaderlodge.games.services import ParticipantInput, record_game
from leaderlodge.groups.locations import resolve_game_location
from leaderlodge.groups.models import Group, GroupPlayer
from leaderlodge.groups.services import resolve_group, resolve_seed_player

SEED_PLAYER_NAMES = ("Nancy", "David")
SCOREKEEPER_GAME_TYPES = frozenset({"dominos", "backgammon"})


@dataclass
class ImportSummary:
    source: str
    game_type_code: str
    parsed: int
    created: int
    skipped: int


def import_source_from_path(path: Path) -> str:
    source = path.stem
    if len(source) > Game._meta.get_field("import_source").max_length:
        raise ValueError(
            f"Import source derived from {path.name!r} is too long "
            f"({len(source)} chars; max "
            f"{Game._meta.get_field('import_source').max_length})."
        )
    return source


def import_row_key(row_number: int) -> str:
    return f"row-{row_number}"


def import_games_file(
    *,
    path: Path,
    group: Group,
    game_type_code: str,
    recorded_by: AbstractBaseUser,
    dry_run: bool = False,
) -> ImportSummary:
    get_game_type(game_type_code)
    if game_type_code in SCOREKEEPER_GAME_TYPES:
        return import_scorekeeper_file(
            path=path,
            group=group,
            game_type_code=game_type_code,
            recorded_by=recorded_by,
            dry_run=dry_run,
        )
    if game_type_code == "progressiverummy":
        return import_progressiverummy_file(
            path=path,
            group=group,
            recorded_by=recorded_by,
            dry_run=dry_run,
        )
    raise ValueError(
        f"No seed importer is configured for game type {game_type_code!r}."
    )


@transaction.atomic
def import_scorekeeper_file(
    *,
    path: Path,
    group: Group,
    game_type_code: str,
    recorded_by: AbstractBaseUser,
    dry_run: bool = False,
) -> ImportSummary:
    rows = parse_scorekeeper_workbook(path)
    import_source = import_source_from_path(path)

    players = {
        name: resolve_seed_player(group=group, seed_name=name)
        for name in SEED_PLAYER_NAMES
    }

    existing_keys = set(
        Game.objects.filter(
            group=group,
            import_source=import_source,
        ).values_list("import_row_key", flat=True)
    )

    created = 0
    skipped = 0

    for row in rows:
        row_key = import_row_key(row.row_number)
        if row_key in existing_keys:
            skipped += 1
            continue

        participant_rows = [
            {
                "player": players["Nancy"],
                "score": row.nancy_score,
            },
            {
                "player": players["David"],
                "score": row.david_score,
            },
        ]
        assign_results_from_scores(participant_rows, game_type_code)

        if dry_run:
            created += 1
            continue

        location = resolve_game_location(
            group=group,
            location_name=row.location_name,
        )
        participants = [
            ParticipantInput(
                player=entry["player"],
                score=entry["score"],
                result=entry["result"],
                placement=entry["placement"],
            )
            for entry in participant_rows
        ]
        record_game(
            user=recorded_by,
            group=group,
            game_type_code=game_type_code,
            played_on=row.played_on,
            participants=participants,
            location=location,
            import_source=import_source,
            import_row_key=row_key,
        )
        created += 1
        existing_keys.add(row_key)

    return ImportSummary(
        source=import_source,
        game_type_code=game_type_code,
        parsed=len(rows),
        created=created,
        skipped=skipped,
    )


def _resolve_import_players(
    *,
    group: Group,
    player_names: set[str],
    cache: dict[str, GroupPlayer],
) -> None:
    for name in player_names:
        if name not in cache:
            cache[name] = resolve_seed_player(group=group, seed_name=name)


@transaction.atomic
def import_progressiverummy_file(
    *,
    path: Path,
    group: Group,
    recorded_by: AbstractBaseUser,
    dry_run: bool = False,
) -> ImportSummary:
    game_type_code = "progressiverummy"
    game_type = get_game_type(game_type_code)
    rows = parse_progressiverummy_workbook(path)
    import_source = import_source_from_path(path)

    player_cache: dict[str, GroupPlayer] = {}
    player_names = {
        player_score.name
        for row in rows
        for player_score in row.player_scores
    }
    _resolve_import_players(
        group=group,
        player_names=player_names,
        cache=player_cache,
    )

    existing_keys = set(
        Game.objects.filter(
            group=group,
            import_source=import_source,
        ).values_list("import_row_key", flat=True)
    )

    created = 0
    skipped = 0

    for row in rows:
        row_key = import_row_key(row.row_number)
        if row_key in existing_keys:
            skipped += 1
            continue

        player_count = len(row.player_scores)
        if not (game_type.min_players <= player_count <= game_type.max_players):
            skipped += 1
            continue

        participant_rows = [
            {
                "player": player_cache[player_score.name],
                "score": player_score.score,
            }
            for player_score in row.player_scores
        ]
        assign_results_from_scores(participant_rows, game_type_code)

        if dry_run:
            created += 1
            continue

        location = resolve_game_location(
            group=group,
            location_name=row.location_name,
        )
        participants = [
            ParticipantInput(
                player=entry["player"],
                score=entry["score"],
                result=entry["result"],
                placement=entry["placement"],
            )
            for entry in participant_rows
        ]
        record_game(
            user=recorded_by,
            group=group,
            game_type_code=game_type_code,
            played_on=row.played_on,
            participants=participants,
            location=location,
            import_source=import_source,
            import_row_key=row_key,
            half_weight=2 if row.is_half else 1,
        )
        created += 1
        existing_keys.add(row_key)

    return ImportSummary(
        source=import_source,
        game_type_code=game_type_code,
        parsed=len(rows),
        created=created,
        skipped=skipped,
    )
