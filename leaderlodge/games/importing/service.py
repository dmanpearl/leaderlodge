from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from django.contrib.auth.models import AbstractBaseUser
from django.db import transaction

from leaderlodge.games.importing.pickleball import (
    parse_pickleball_workbook,
    resolve_import_side,
    sides_have_shared_members,
)
from leaderlodge.games.importing.progressiverummy import (
    ProgressiveRummyRow,
    parse_progressiverummy_workbook,
)
from leaderlodge.games.importing.scorekeeper import (
    ScoreKeeperRow,
    parse_scorekeeper_workbook,
)
from leaderlodge.games.models import Game
from leaderlodge.games.registry import get_game_type
from leaderlodge.games.scoring import assign_results_from_scores
from leaderlodge.games.services import ParticipantInput, record_game
from leaderlodge.groups.demo_seed_locations import geo_for_seed_location
from leaderlodge.groups.locations import resolve_game_location
from leaderlodge.groups.models import Group, GroupPlayer
from leaderlodge.groups.services import resolve_group, resolve_seed_player

SCOREKEEPER_GAME_TYPES = frozenset({"dominos", "backgammon"})
RAW_GAMES_GAME_TYPES = frozenset(
    {
        "progressiverummy",
        "mahjongg",
        "ginrummy",
        "cribbage",
        "phase10",
        "darts",
        "cornhole",
    }
)
PICKLEBALL_GAME_TYPE = "pickleball"


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
    if game_type_code in RAW_GAMES_GAME_TYPES:
        return import_raw_games_file(
            path=path,
            group=group,
            game_type_code=game_type_code,
            recorded_by=recorded_by,
            dry_run=dry_run,
        )
    if game_type_code == PICKLEBALL_GAME_TYPE:
        return import_pickleball_file(
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
    parsed = parse_scorekeeper_workbook(path)
    import_source = import_source_from_path(path)

    players = {
        name: resolve_seed_player(group=group, seed_name=name)
        for name in parsed.player_names
    }

    existing_keys = set(
        Game.objects.filter(
            group=group,
            import_source=import_source,
        ).values_list("import_row_key", flat=True)
    )

    created = 0
    skipped = 0

    for row in parsed.rows:
        row_key = import_row_key(row.row_number)
        if row_key in existing_keys:
            skipped += 1
            continue

        participant_rows = [
            {
                "player": players[name],
                "score": score,
            }
            for name, score in zip(parsed.player_names, row.scores, strict=True)
        ]
        assign_results_from_scores(participant_rows, game_type_code)

        if dry_run:
            created += 1
            continue

        location = resolve_game_location(
            group=group,
            location_name=row.location_name,
            geo=geo_for_seed_location(row.location_name),
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
        parsed=len(parsed.rows),
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
def import_raw_games_file(
    *,
    path: Path,
    group: Group,
    game_type_code: str,
    recorded_by: AbstractBaseUser,
    dry_run: bool = False,
) -> ImportSummary:
    game_type = get_game_type(game_type_code)
    rows = parse_progressiverummy_workbook(path)
    import_source = import_source_from_path(path)
    use_half_games = game_type_code == "progressiverummy"

    player_cache: dict[str, GroupPlayer] = {}
    player_names = {
        player_score.name for row in rows for player_score in row.player_scores
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
            geo=geo_for_seed_location(row.location_name),
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
            half_weight=2 if use_half_games and row.is_half else 1,
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


@transaction.atomic
def import_progressiverummy_file(
    *,
    path: Path,
    group: Group,
    recorded_by: AbstractBaseUser,
    dry_run: bool = False,
) -> ImportSummary:
    return import_raw_games_file(
        path=path,
        group=group,
        game_type_code="progressiverummy",
        recorded_by=recorded_by,
        dry_run=dry_run,
    )


@transaction.atomic
def import_mahjongg_file(
    *,
    path: Path,
    group: Group,
    recorded_by: AbstractBaseUser,
    dry_run: bool = False,
) -> ImportSummary:
    return import_raw_games_file(
        path=path,
        group=group,
        game_type_code="mahjongg",
        recorded_by=recorded_by,
        dry_run=dry_run,
    )


@transaction.atomic
def import_pickleball_file(
    *,
    path: Path,
    group: Group,
    recorded_by: AbstractBaseUser,
    dry_run: bool = False,
) -> ImportSummary:
    game_type = get_game_type(PICKLEBALL_GAME_TYPE)
    rows = parse_pickleball_workbook(path)
    import_source = import_source_from_path(path)

    side_cache: dict[str, GroupPlayer] = {}
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

        player_count = len(row.side_scores)
        if not (game_type.min_players <= player_count <= game_type.max_players):
            skipped += 1
            continue

        side_labels = [side_score.label for side_score in row.side_scores]
        if sides_have_shared_members(side_labels):
            skipped += 1
            continue

        participant_rows = [
            {
                "player": resolve_import_side(
                    group=group,
                    side_label=side_score.label,
                    cache=side_cache,
                ),
                "score": side_score.score,
            }
            for side_score in row.side_scores
        ]
        assign_results_from_scores(participant_rows, PICKLEBALL_GAME_TYPE)

        if dry_run:
            created += 1
            continue

        location = resolve_game_location(
            group=group,
            location_name=row.location_name,
            geo=geo_for_seed_location(row.location_name),
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
            game_type_code=PICKLEBALL_GAME_TYPE,
            played_on=row.played_on,
            participants=participants,
            location=location,
            import_source=import_source,
            import_row_key=row_key,
            score_type=row.score_type,
        )
        created += 1
        existing_keys.add(row_key)

    return ImportSummary(
        source=import_source,
        game_type_code=PICKLEBALL_GAME_TYPE,
        parsed=len(rows),
        created=created,
        skipped=skipped,
    )
