from django.core.management.base import BaseCommand, CommandError

from leaderlodge.groups.sync_locations import (
    resolve_group_by_name,
    sync_group_locations,
)


class Command(BaseCommand):
    help = (
        "Copy location names and geo from a source group onto matching locations "
        "in a destination group. Infers combines when multiple destination "
        "locations match one source location. Does not create missing locations. "
        "Does not share location libraries."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--src",
            required=True,
            help="Source group name (e.g. manpearl). Location state is copied from here.",
        )
        parser.add_argument(
            "--dst",
            required=True,
            help="Destination group name (e.g. Demo). Matching locations are updated.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview matches, combines, and updates without writing.",
        )

    def handle(self, *args, **options):
        try:
            source = resolve_group_by_name(options["src"])
            dest = resolve_group_by_name(options["dst"])
            summary = sync_group_locations(
                source_group=source,
                dest_group=dest,
                dry_run=options["dry_run"],
            )
        except ValueError as exc:
            raise CommandError(str(exc)) from exc

        prefix = "Dry run" if summary.dry_run else "Sync"
        self.stdout.write(
            f"{prefix}: {summary.source_group!r} -> {summary.dest_group!r}"
        )

        if summary.actions:
            self.stdout.write("Actions:")
            for action in summary.actions:
                self.stdout.write(f"  [{action.kind}] {action.detail}")
        else:
            self.stdout.write("  (no updates or combines)")

        if summary.skipped_src:
            self.stdout.write(
                self.style.WARNING(
                    "Skipped source locations with no destination match:"
                )
            )
            for name in sorted(summary.skipped_src):
                self.stdout.write(f"  - {name}")

        if summary.unmatched_dst:
            self.stdout.write(
                self.style.WARNING(
                    "Destination locations with no source match (left unchanged):"
                )
            )
            for name in summary.unmatched_dst:
                self.stdout.write(f"  - {name}")

        if summary.ambiguous:
            self.stdout.write(self.style.WARNING("Ambiguous matches (skipped):"))
            for note in summary.ambiguous:
                self.stdout.write(f"  - {note}")

        self.stdout.write(
            self.style.SUCCESS(
                f"Done: combined={summary.combined}, updated={summary.updated}, "
                f"skipped_src={len(summary.skipped_src)}, "
                f"unmatched_dst={len(summary.unmatched_dst)}"
            )
        )
