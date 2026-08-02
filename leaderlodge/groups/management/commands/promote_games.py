from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from leaderlodge.games.registry import GAME_TYPES
from leaderlodge.groups.demo_promotion import (
    promote_games,
    purge_promoted_games,
)
from leaderlodge.groups.demo_promotion_locations import (
    DEST_GROUP_NAME,
    SOURCE_GROUP_NAME,
)
from leaderlodge.groups.models import Group
from leaderlodge.groups.services import resolve_group


class Command(BaseCommand):
    help = (
        "Promote games from a source group (default: manpearl) into the "
        "public Demo group, applying player name and location anonymization "
        "(see demo_promotion_names.py and demo_promotion_locations.py). "
        "Idempotent: re-running only adds games that were not already promoted."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--source-group",
            default=SOURCE_GROUP_NAME,
            help=f"Source group name or primary key. Defaults to {SOURCE_GROUP_NAME!r}.",
        )
        parser.add_argument(
            "--dest-group",
            default=DEST_GROUP_NAME,
            help=f"Destination group name or primary key. Defaults to {DEST_GROUP_NAME!r}.",
        )
        parser.add_argument(
            "--game-type",
            choices=sorted(GAME_TYPES),
            help="Only promote games of this type. Defaults to all game types.",
        )
        parser.add_argument(
            "--recorded-by",
            help=(
                "Username to store as recorder on promoted games. "
                "Defaults to the destination group owner."
            ),
        )
        parser.add_argument(
            "--purge",
            action="store_true",
            help=(
                "Delete all previously promoted games from the destination "
                "group before promoting, for a clean full redo."
            ),
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would happen without writing to the database.",
        )

    def handle(self, *args, **options):
        try:
            source_group = resolve_group(options["source_group"])
            dest_group = resolve_group(options["dest_group"])
        except Group.DoesNotExist as exc:
            raise CommandError(str(exc)) from exc

        recorded_by = dest_group.created_by
        if options["recorded_by"]:
            User = get_user_model()
            recorded_by = User.objects.filter(username=options["recorded_by"]).first()
            if recorded_by is None:
                raise CommandError(f'No user with username {options["recorded_by"]!r}.')

        if options["purge"]:
            if options["dry_run"]:
                self.stdout.write(
                    "Dry run, would purge previously promoted games from "
                    f"{dest_group.name!r} before promoting."
                )
            else:
                purged = purge_promoted_games(
                    source_group=source_group, dest_group=dest_group
                )
                self.stdout.write(
                    f"Purged {purged} previously promoted game(s) from "
                    f"{dest_group.name!r}."
                )

        summary = promote_games(
            source_group=source_group,
            dest_group=dest_group,
            recorded_by=recorded_by,
            game_type_code=options["game_type"],
            dry_run=options["dry_run"],
        )

        mode = "Dry run" if options["dry_run"] else "Promotion"
        self.stdout.write(
            f"{mode} complete for {source_group.name!r} into {dest_group.name!r}"
            + (f" ({summary.game_type_code})" if summary.game_type_code else "")
            + "."
        )
        self.stdout.write(f"  Source games seen: {summary.total_source_games}")
        self.stdout.write(f"  Created:           {summary.created}")
        self.stdout.write(f"  Already promoted:  {summary.already_promoted}")
        self.stdout.write(
            f"  Skipped (no name mapping): {summary.skipped_unmapped_player}"
        )

        if summary.unmapped_player_names:
            self.stdout.write("")
            self.stdout.write(
                self.style.WARNING(
                    "The following source players have no entry in "
                    "demo_promotion_names.PLAYER_NAME_MAP. Their games were "
                    "skipped; add them and re-run to include those games:"
                )
            )
            for name in sorted(summary.unmapped_player_names):
                self.stdout.write(f"  - {name}")
