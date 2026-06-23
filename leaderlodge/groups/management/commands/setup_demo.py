from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from leaderlodge.games.importing.service import import_games_file
from leaderlodge.groups.demo import (
    DEMO_GROUP_DESCRIPTION,
    DEMO_GROUP_NAME,
    demo_seed_paths,
)
from leaderlodge.groups.models import Group
from leaderlodge.groups.services import create_group_with_owner


class Command(BaseCommand):
    help = (
        "Create or update the public Demo group, set is_demo=True, "
        "and import all bundled demo seed spreadsheets."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--owner",
            help=(
                "Username for the Demo group owner (imports run as this user). "
                "Defaults to the first superuser."
            ),
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Validate seed files and report actions without writing to the database.",
        )

    def handle(self, *args, **options):
        owner = self._resolve_owner(options["owner"])
        group = self._ensure_demo_group(owner=owner, dry_run=options["dry_run"])

        if options["dry_run"]:
            self.stdout.write(
                self.style.WARNING(
                    f"Dry run — would import demo seeds into group {group.name!r}."
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Demo group {group.name!r} is ready (is_demo=True, owner={owner.username})."
                )
            )

        missing = []
        for game_type, path in demo_seed_paths(settings.BASE_DIR):
            if not path.is_file():
                missing.append(str(path.relative_to(settings.BASE_DIR)))
                continue
            if options["dry_run"]:
                self.stdout.write(f"  Would import {path.name} ({game_type})")
                continue
            summary = import_games_file(
                path=path,
                group=group,
                game_type_code=game_type,
                recorded_by=owner,
            )
            self.stdout.write(
                f"  {path.name} ({game_type}): "
                f"parsed={summary.parsed}, created={summary.created}, skipped={summary.skipped}"
            )

        if missing:
            raise CommandError(
                "Missing demo seed file(s):\n  "
                + "\n  ".join(missing)
                + "\nEnsure demo spreadsheets are present in the deployed checkout."
            )

    def _resolve_owner(self, username: str | None):
        User = get_user_model()
        if username:
            owner = User.objects.filter(username=username).first()
            if owner is None:
                raise CommandError(f"No user with username {username!r}.")
            return owner

        owner = User.objects.filter(is_superuser=True).order_by("pk").first()
        if owner is None:
            raise CommandError(
                "No superuser found. Run createsuperuser first, or pass --owner USERNAME."
            )
        return owner

    def _ensure_demo_group(self, *, owner, dry_run: bool) -> Group:
        group = Group.objects.filter(name=DEMO_GROUP_NAME).first()
        if group is None:
            if dry_run:
                self.stdout.write(
                    f"Would create group {DEMO_GROUP_NAME!r} owned by {owner.username} "
                    f"with is_demo=True."
                )
                return Group(name=DEMO_GROUP_NAME, is_demo=True, created_by=owner)

            group = create_group_with_owner(
                user=owner,
                name=DEMO_GROUP_NAME,
                description=DEMO_GROUP_DESCRIPTION,
            )
            group.is_demo = True
            group.save(update_fields=["is_demo"])
            self.stdout.write(f"Created group {DEMO_GROUP_NAME!r}.")
            return group

        updates = []
        if not group.is_demo:
            updates.append("is_demo=True")
            if not dry_run:
                group.is_demo = True
                group.save(update_fields=["is_demo"])

        if group.description != DEMO_GROUP_DESCRIPTION:
            updates.append("description")
            if not dry_run:
                group.description = DEMO_GROUP_DESCRIPTION
                group.save(update_fields=["description"])

        if updates:
            action = "Would update" if dry_run else "Updated"
            self.stdout.write(f"{action} group {DEMO_GROUP_NAME!r}: {', '.join(updates)}.")
        else:
            self.stdout.write(f"Group {DEMO_GROUP_NAME!r} already exists with is_demo=True.")

        return group
