from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from django.contrib.auth.models import AbstractBaseUser
from django.db import transaction

from leaderlodge.games.importing.scorekeeper import ScoreKeeperRow, parse_scorekeeper_workbook
from leaderlodge.games.models import Game
from leaderlodge.games.registry import get_game_type
from leaderlodge.games.scoring import assign_results_from_scores
from leaderlodge.games.services import ParticipantInput, record_game
from leaderlodge.groups.locations import resolve_game_location
from leaderlodge.groups.models import Group, GroupPlayer
from leaderlodge.groups.services import resolve_group, resolve_seed_player

SEED_PLAYER_NAMES = ("Nancy", "David")


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


def import_row_key(row: ScoreKeeperRow) -> str:
    return f"row-{row.row_number}"


@transaction.atomic
def import_scorekeeper_file(
    *,
    path: Path,
    group: Group,
    game_type_code: str,
    recorded_by: AbstractBaseUser,
    dry_run: bool = False,
) -> ImportSummary:
    get_game_type(game_type_code)
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
        row_key = import_row_key(row)
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
