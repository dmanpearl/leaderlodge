from django.core.management.base import BaseCommand, CommandError

from leaderlodge.games.models import Game
from leaderlodge.games.score_changes import change_game_score
from leaderlodge.groups.models import GroupPlayer


class Command(BaseCommand):
    help = (
        "Change one participant score on a game, recalculate results and placements, "
        "and record an audit log entry."
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
        game = Game.objects.filter(pk=options["game"]).first()
        if game is None:
            raise CommandError(f"No game with pk={options['game']}.")

        player = self._resolve_player(game, options["player"])
        user = self._resolve_user(options["changed_by"])
        participant = game.participant_results.filter(player=player).first()
        if participant is None:
            raise CommandError(f"{player.display_label} is not in game {game.pk}.")

        if participant.score == options["score"]:
            raise CommandError("New score matches the current score.")

        try:
            summary = change_game_score(
                game=game,
                user=user,
                player=player,
                new_score=options["score"],
                notes=options["notes"],
                dry_run=options["dry_run"],
            )
        except Exception as exc:
            raise CommandError(str(exc)) from exc
        self._write_summary(summary, dry_run=options["dry_run"])

    def _write_summary(self, summary, *, dry_run: bool) -> None:
        if not summary.logs:
            self.stdout.write(
                self.style.WARNING(
                    f"No changes for game {summary.game.pk}; "
                    "score already produced the same results."
                )
            )
            return

        prefix = "Would update" if dry_run else "Updated"
        self.stdout.write(
            f"{prefix} game {summary.game.pk}: "
            f"{summary.participants_updated} participant(s)"
            + (", double weight changed" if summary.double_weight_changed else "")
        )
        for log in summary.logs:
            if log.participant_result_id:
                self.stdout.write(
                    f"  {log.player.display_label}: score {log.old_score} -> {log.new_score}, "
                    f"result {log.old_result or '-'} -> {log.new_result or '-'}, "
                    f"placement {log.old_placement} -> {log.new_placement}"
                )
            else:
                self.stdout.write(
                    f"  double weight {log.old_double_weight} -> {log.new_double_weight}"
                )

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
