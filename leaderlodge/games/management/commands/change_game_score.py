from django.core.management.base import BaseCommand, CommandError

from leaderlodge.games.models import Game
from leaderlodge.games.score_changes import _UNCHANGED, apply_game_edits
from leaderlodge.groups.locations import resolve_game_location
from leaderlodge.groups.models import GroupPlayer


class Command(BaseCommand):
    help = (
        "Change one participant score on a game, optionally update location, "
        "recalculate results and placements, and record audit log entries."
    )

    def add_arguments(self, parser):
        parser.add_argument("--game", type=int, required=True, help="Game primary key.")
        parser.add_argument(
            "--player",
            required=True,
            help="Participant player primary key or display name.",
        )
        parser.add_argument("--score", type=int, required=True, help="New score value.")
        parser.add_argument(
            "--location",
            default=None,
            help="Optional new location name. Pass an empty string to clear.",
        )
        parser.add_argument(
            "--changed-by",
            required=True,
            help="Username of the staff member making the change.",
        )
        parser.add_argument(
            "--notes",
            required=True,
            help="Required note explaining why the score was changed.",
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

        player = self._resolve_player(game, options["player"])
        user = self._resolve_user(options["changed_by"])
        participant = game.participant_results.filter(player=player).first()
        if participant is None:
            raise CommandError(f"{player.display_label} is not in game {game.pk}.")

        score_updates = {}
        if participant.score != options["score"]:
            score_updates[player.pk] = options["score"]

        new_location = _UNCHANGED
        if options["location"] is not None:
            new_location = resolve_game_location(
                group=game.group,
                location_name=options["location"],
            )

        if not score_updates and new_location is _UNCHANGED:
            raise CommandError("No score or location change requested.")
        if (
            not score_updates
            and new_location is not _UNCHANGED
            and game.location == new_location
        ):
            raise CommandError("New location matches the current location.")

        try:
            summary = apply_game_edits(
                game=game,
                user=user,
                notes=options["notes"],
                score_updates=score_updates or None,
                new_location=new_location,
                dry_run=options["dry_run"],
            )
        except Exception as exc:
            raise CommandError(str(exc)) from exc
        self._write_summary(summary, dry_run=options["dry_run"])

    def _write_summary(self, summary, *, dry_run: bool) -> None:
        if summary.log is None:
            self.stdout.write(
                self.style.WARNING(
                    f"No changes for game {summary.game.pk}; "
                    "requested edits produced no audit row."
                )
            )
            return

        prefix = "Would update" if dry_run else "Updated"
        parts = []
        if summary.participants_updated:
            parts.append(f"{summary.participants_updated} participant(s)")
        if summary.double_weight_changed:
            parts.append("double weight changed")
        if summary.location_changed:
            parts.append("location changed")
        self.stdout.write(f"{prefix} game {summary.game.pk}: {', '.join(parts)}")
        self.stdout.write("  Audit log recorded.")

    def _resolve_player(self, game: Game, raw_player: str) -> GroupPlayer:
        if raw_player.isdigit():
            player = GroupPlayer.objects.filter(
                pk=int(raw_player),
                group_id=game.group_id,
            ).first()
            if player is not None:
                return player

        player = GroupPlayer.objects.filter(
            group_id=game.group_id,
            display_name__iexact=raw_player.strip(),
        ).first()
        if player is None:
            raise CommandError(
                f"No player {raw_player!r} found in group {game.group.name!r}."
            )
        return player

    def _resolve_user(self, username: str):
        from django.contrib.auth import get_user_model

        User = get_user_model()
        user = User.objects.filter(username=username).first()
        if user is None:
            raise CommandError(f"No user with username {username!r}.")
        if not (user.is_staff or user.is_superuser):
            raise CommandError(f"User {username!r} must be staff.")
        return user
