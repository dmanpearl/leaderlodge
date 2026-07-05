from django.core.management.base import BaseCommand, CommandError

from leaderlodge.games.models import Game
from leaderlodge.games.score_changes import apply_game_edits
from leaderlodge.groups.locations import resolve_game_location


class Command(BaseCommand):
    help = "Change a game's location and record an audit log entry."

    def add_arguments(self, parser):
        parser.add_argument("--game", type=int, required=True, help="Game primary key.")
        parser.add_argument(
            "--location",
            default="",
            help="New location name. Use an empty value to clear the location.",
        )
        parser.add_argument(
            "--changed-by",
            required=True,
            help="Username of the staff member making the change.",
        )
        parser.add_argument(
            "--notes",
            required=True,
            help="Required note explaining why the location was changed.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Validate and preview changes without writing to the database.",
        )

    def handle(self, *args, **options):
        game = (
            Game.objects.select_related("group", "location")
            .filter(pk=options["game"])
            .first()
        )
        if game is None:
            raise CommandError(f"No game with pk={options['game']}.")

        user = self._resolve_user(options["changed_by"])
        new_location = resolve_game_location(
            group=game.group,
            location_name=options["location"],
        )
        if game.location == new_location:
            raise CommandError("New location matches the current location.")

        try:
            summary = apply_game_edits(
                game=game,
                user=user,
                notes=options["notes"],
                score_updates={},
                new_location=new_location,
                dry_run=options["dry_run"],
            )
        except Exception as exc:
            raise CommandError(str(exc)) from exc

        prefix = "Would update" if options["dry_run"] else "Updated"
        old_name = game.location.name if game.location_id else "(none)"
        new_name = new_location.name if new_location is not None else "(none)"
        self.stdout.write(
            self.style.SUCCESS(
                f"{prefix} game {game.pk} location: {old_name} -> {new_name}"
            )
        )
        if summary.logs:
            self.stdout.write(f"  wrote {len(summary.logs)} audit log row(s)")

    def _resolve_user(self, username: str):
        from django.contrib.auth import get_user_model

        User = get_user_model()
        user = User.objects.filter(username=username).first()
        if user is None:
            raise CommandError(f"No user with username {username!r}.")
        if not (user.is_staff or user.is_superuser):
            raise CommandError(f"User {username!r} must be staff.")
        return user
