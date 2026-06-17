from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from leaderlodge.games.importing.service import import_games_file
from leaderlodge.games.registry import GAME_TYPES
from leaderlodge.groups.models import Group
from leaderlodge.groups.services import resolve_group


class Command(BaseCommand):
    help = (
        "Import games from a ScoreKeeper spreadsheet (.xlsx). "
        "The file path is required; no default seed file is assumed."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "spreadsheet",
            help="Path to the .xlsx file to import.",
        )
        parser.add_argument(
            "-g",
            "--group",
            required=True,
            help="Target group name or primary key.",
        )
        parser.add_argument(
            "--game-type",
            required=True,
            choices=sorted(GAME_TYPES),
            help="Game type code for the rows in this spreadsheet.",
        )
        parser.add_argument(
            "--recorded-by",
            help=(
                "Username of the user to store as recorder. "
                "Defaults to the group owner."
            ),
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Parse and validate rows without writing to the database.",
        )

    def handle(self, *args, **options):
        path = Path(options["spreadsheet"]).expanduser()
        if not path.is_file():
            raise CommandError(f"Spreadsheet not found: {path}")

        if path.suffix.lower() != ".xlsx":
            raise CommandError(f"Expected an .xlsx file, got: {path.name}")

        try:
            group = resolve_group(options["group"])
        except Group.DoesNotExist as exc:
            raise CommandError(str(exc)) from exc

        recorded_by = group.created_by
        if options["recorded_by"]:
            from django.contrib.auth import get_user_model

            User = get_user_model()
            recorded_by = User.objects.filter(
                username=options["recorded_by"]
            ).first()
            if recorded_by is None:
                raise CommandError(
                    f'No user with username {options["recorded_by"]!r}.'
                )

        try:
            summary = import_games_file(
                path=path,
                group=group,
                game_type_code=options["game_type"],
                recorded_by=recorded_by,
                dry_run=options["dry_run"],
            )
        except ValueError as exc:
            raise CommandError(str(exc)) from exc

        mode = "Dry run" if options["dry_run"] else "Import"
        self.stdout.write(
            f"{mode} complete for {path.name} "
            f"({summary.game_type_code}) -> group {group.name!r} "
            f"[source={summary.source}]"
        )
        self.stdout.write(f"  Parsed:  {summary.parsed}")
        self.stdout.write(f"  Created: {summary.created}")
        self.stdout.write(f"  Skipped: {summary.skipped}")
