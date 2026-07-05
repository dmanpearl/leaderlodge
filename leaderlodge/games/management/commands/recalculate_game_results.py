from django.core.management.base import BaseCommand, CommandError

from leaderlodge.games.models import Game, GameScoreChangeLog
from leaderlodge.games.registry import GAME_TYPES
from leaderlodge.games.score_changes import recalculate_game_results
from leaderlodge.groups.services import resolve_group


class Command(BaseCommand):
    help = (
        "Recalculate participant results, placements, and double weight from existing "
        "scores using current registry rules."
    )

    def add_arguments(self, parser):
        parser.add_argument("--game", type=int, help="Single game primary key.")
        parser.add_argument(
            "--game-type",
            choices=sorted(GAME_TYPES),
            help="Recalculate all games of this type.",
        )
        parser.add_argument(
            "-g",
            "--group",
            help="Limit --game-type recalculations to one group name or primary key.",
        )
        parser.add_argument(
            "--all",
            action="store_true",
            help="Recalculate every game in the database.",
        )
        parser.add_argument(
            "--changed-by",
            required=True,
            help="Username of the staff member performing the recalculation.",
        )
        parser.add_argument(
            "--notes",
            required=True,
            help="Required note explaining why results were recalculated.",
        )
        parser.add_argument(
            "--change-type",
            choices=[
                GameScoreChangeLog.ChangeType.RECALCULATE,
                GameScoreChangeLog.ChangeType.SCORE_CHANGE,
            ],
            default=GameScoreChangeLog.ChangeType.RECALCULATE,
            help="Audit log change type to record.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Validate and preview changes without writing to the database.",
        )

    def handle(self, *args, **options):
        games = self._resolve_games(options)
        user = self._resolve_user(options["changed_by"])

        total_games = 0
        total_logs = 0
        for game in games:
            try:
                summary = recalculate_game_results(
                    game=game,
                    user=user,
                    notes=options["notes"],
                    change_type=options["change_type"],
                    dry_run=options["dry_run"],
                )
            except Exception as exc:
                raise CommandError(f"Game {game.pk}: {exc}") from exc

            if not summary.logs:
                continue

            total_games += 1
            total_logs += len(summary.logs)
            prefix = "Would update" if options["dry_run"] else "Updated"
            self.stdout.write(
                f"{prefix} game {game.pk} ({game.game_type_code} on {game.played_on}): "
                f"{summary.participants_updated} participant(s)"
                + (", double weight changed" if summary.double_weight_changed else "")
            )

        if total_games == 0:
            self.stdout.write(self.style.WARNING("No games required recalculation."))
            return

        self.stdout.write(
            self.style.SUCCESS(
                f"{'Would change' if options['dry_run'] else 'Changed'} "
                f"{total_logs} log row(s) across {total_games} game(s)."
            )
        )

    def _resolve_games(self, options) -> list[Game]:
        selected = sum(bool(options[key]) for key in ("game", "game_type", "all"))
        if selected != 1:
            raise CommandError("Specify exactly one of --game, --game-type, or --all.")

        if options["game"]:
            game = Game.objects.filter(pk=options["game"]).first()
            if game is None:
                raise CommandError(f"No game with pk={options['game']}.")
            return [game]

        queryset = Game.objects.order_by("pk")
        if options["game_type"]:
            queryset = queryset.filter(game_type_code=options["game_type"])
        if options["group"]:
            try:
                group = resolve_group(options["group"])
            except Exception as exc:
                raise CommandError(str(exc)) from exc
            queryset = queryset.filter(group=group)
        return list(queryset)

    def _resolve_user(self, username: str):
        from django.contrib.auth import get_user_model

        User = get_user_model()
        user = User.objects.filter(username=username).first()
        if user is None:
            raise CommandError(f"No user with username {username!r}.")
        if not (user.is_staff or user.is_superuser):
            raise CommandError(f"User {username!r} must be staff.")
        return user
