from django.core.management.base import BaseCommand, CommandError

from leaderlodge.accounts.fake_accounts import (
    DEFAULT_MIN_SCORE,
    deactivate_users,
    delete_users,
    find_fake_account_candidates,
)


class Command(BaseCommand):
    help = (
        "Identify likely fake / spam user accounts (random usernames, no "
        "engagement). Default is report-only across active and inactive "
        "users; use --active-only to limit to accounts that can still log "
        "in. Use --deactivate to flag or --delete to hard-remove accounts "
        "with no PROTECT relations."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--min-score",
            type=int,
            default=DEFAULT_MIN_SCORE,
            help=(
                f"Minimum spam score to include (default {DEFAULT_MIN_SCORE}). "
                "Random-looking usernames alone score 3."
            ),
        )
        parser.add_argument(
            "--username",
            action="append",
            dest="usernames",
            default=None,
            help="Limit to this username (repeatable).",
        )
        parser.add_argument(
            "--active-only",
            action="store_true",
            help="Only include currently active users (can still log in).",
        )
        parser.add_argument(
            "--include-engaged",
            action="store_true",
            help=(
                "Do not exclude users with memberships/games/invites. "
                "Still never hard-deletes engaged accounts."
            ),
        )
        parser.add_argument(
            "--deactivate",
            action="store_true",
            help="Set is_active=False on matching candidates and log AuthEvents.",
        )
        parser.add_argument(
            "--delete",
            action="store_true",
            help=(
                "Hard-delete matching candidates that have no PROTECT "
                "relations. Mutually exclusive with --deactivate."
            ),
        )

    def handle(self, *args, **options):
        if options["deactivate"] and options["delete"]:
            raise CommandError("Use either --deactivate or --delete, not both.")

        candidates = find_fake_account_candidates(
            min_score=options["min_score"],
            active_only=options["active_only"],
            usernames=options["usernames"],
            require_no_engagement=not options["include_engaged"],
        )

        if not candidates:
            self.stdout.write("No matching fake-account candidates.")
            return

        self._print_report(candidates)

        if options["deactivate"]:
            users = [c.user for c in candidates]
            changed = deactivate_users(users)
            self.stdout.write(self.style.SUCCESS(f"Deactivated {changed} user(s)."))
            return

        if options["delete"]:
            users = [c.user for c in candidates]
            deleted, skipped = delete_users(users)
            self.stdout.write(self.style.SUCCESS(f"Deleted {deleted} user(s)."))
            for user, reason in skipped:
                self.stdout.write(
                    self.style.WARNING(f"Skipped {user.get_username()}: {reason}")
                )
            return

        self.stdout.write(
            "Report only. Pass --deactivate to flag or --delete to remove "
            "safe accounts."
        )

    def _print_report(self, candidates) -> None:
        self.stdout.write(f"Found {len(candidates)} candidate(s):\n")
        for c in candidates:
            user = c.user
            delete_note = (
                "deletable"
                if c.can_delete
                else f"delete blocked ({', '.join(c.delete_blockers)})"
            )
            active = "active" if user.is_active else "inactive"
            self.stdout.write(
                f"  score={c.score}  {user.get_username()!r}  "
                f"<{user.email or '-'}>  {active}  {delete_note}"
            )
            self.stdout.write(f"    {c.reason_summary}")
            self.stdout.write(
                f"    joined={user.date_joined:%Y-%m-%d}  "
                f"last_login={user.last_login or '-'}"
            )
        self.stdout.write("")
