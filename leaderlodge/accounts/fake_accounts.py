"""Identify and clean up likely fake / spam user accounts.

Designed for bot signups that look like username ``myylprhhgz`` with little
or no real engagement (no group memberships, no recorded games, etc.).

Default action is report-only. Deactivate (flag) is the safe cleanup path;
hard delete is only offered when no PROTECT relations would block it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from django.contrib.auth import get_user_model
from django.db.models import Count, QuerySet

from leaderlodge.accounts.auth_log import record_auth_event
from leaderlodge.accounts.models import AuthEvent
from leaderlodge.accounts.registration import username_base_from_email

User = get_user_model()

# Relations that PROTECT user deletion. Count > 0 means hard delete fails.
_PROTECT_RELATIONS: tuple[tuple[str, str], ...] = (
    ("created_groups", "created groups"),
    ("recorded_games", "recorded games"),
    ("sent_group_invites", "sent invites"),
    ("feedback_submissions", "feedback"),
    ("assigned_feedback", "assigned feedback"),
    ("game_score_changes", "score change logs"),
    ("location_libraries", "location libraries"),
)

# Engagement that means the account is almost certainly real (or at least
# not safe to auto-flag). These users are excluded from candidates.
_ENGAGEMENT_RELATIONS: tuple[str, ...] = (
    "group_memberships",
    "created_groups",
    "recorded_games",
    "sent_group_invites",
    "feedback_submissions",
    "accepted_group_invites",
)

_VOWELS = set("aeiouy")
_RANDOM_ALPHA_RE = re.compile(r"^[a-z]{8,}$")

# Score threshold: random username or bot-generated names alone (>= 3) is
# enough; weaker signals need to stack.
DEFAULT_MIN_SCORE = 3


@dataclass(frozen=True)
class FakeAccountSignal:
    key: str
    points: int
    detail: str


@dataclass
class FakeAccountCandidate:
    user: object
    score: int
    signals: list[FakeAccountSignal] = field(default_factory=list)
    delete_blockers: list[str] = field(default_factory=list)

    @property
    def can_delete(self) -> bool:
        return not self.delete_blockers

    @property
    def reason_summary(self) -> str:
        return "; ".join(s.detail for s in self.signals)


def looks_like_random_alpha(token: str, *, max_vowel_ratio: float = 0.4) -> bool:
    """True for long lowercase a-z tokens with few vowels (bot gibberish)."""
    name = (token or "").strip().lower()
    if not _RANDOM_ALPHA_RE.fullmatch(name):
        return False
    vowel_count = sum(1 for ch in name if ch in _VOWELS)
    return (vowel_count / len(name)) <= max_vowel_ratio


def username_looks_random(username: str) -> bool:
    """Heuristic for consonant-soup bot usernames like ``myylprhhgz``."""
    return looks_like_random_alpha(username)


def names_look_bot_generated(first_name: str, last_name: str) -> bool:
    """Both first and last look like lowercase gibberish (common spam pattern).

    Real roster names are usually title-cased. Bots often fill both fields with
    random lowercase alpha strings (e.g. ``lqeghxyefp`` / ``lqkluxifvs``).
    """
    first = (first_name or "").strip()
    last = (last_name or "").strip()
    if not first or not last:
        return False
    if first != first.lower() or last != last.lower():
        return False
    return looks_like_random_alpha(first) and looks_like_random_alpha(last)


def username_mismatches_email(username: str, email: str) -> bool:
    """True when username is not the email-local form current signup would use."""
    email = (email or "").strip()
    if not email or "@" not in email:
        return False
    base = username_base_from_email(email)
    name = (username or "").strip().lower()
    if name == base:
        return False
    # Allow signup collision suffixes: l.parks2, l.parks3, ...
    if name.startswith(base) and name[len(base) :].isdigit():
        return False
    return True


def _annotate_engagement(qs: QuerySet) -> QuerySet:
    annotations = {
        f"_{rel}_count": Count(rel, distinct=True) for rel in _ENGAGEMENT_RELATIONS
    }
    annotations.update(
        {f"_{rel}_count": Count(rel, distinct=True) for rel, _ in _PROTECT_RELATIONS}
    )
    annotations["_linked_player_games"] = Count(
        "group_player_profiles__game_results",
        distinct=True,
    )
    return qs.annotate(**annotations)


def _has_engagement(user) -> bool:
    if any(getattr(user, f"_{rel}_count", 0) > 0 for rel in _ENGAGEMENT_RELATIONS):
        return True
    if getattr(user, "_linked_player_games", 0) > 0:
        return True
    return False


def _delete_blockers(user) -> list[str]:
    blockers: list[str] = []
    for rel, label in _PROTECT_RELATIONS:
        if getattr(user, f"_{rel}_count", 0) > 0:
            blockers.append(label)
    return blockers


def _email_verified(user) -> bool:
    profile = getattr(user, "profile", None)
    return profile is not None and profile.email_verified_at is not None


def score_user(user) -> list[FakeAccountSignal]:
    """Return spam signals for a user (does not apply engagement gate)."""
    signals: list[FakeAccountSignal] = []
    username = user.get_username()
    email = (user.email or "").strip()
    first_name = (user.first_name or "").strip()
    last_name = (user.last_name or "").strip()

    if username_looks_random(username):
        signals.append(
            FakeAccountSignal(
                "random_username",
                3,
                f"random-looking username ({username})",
            )
        )

    if names_look_bot_generated(first_name, last_name):
        signals.append(
            FakeAccountSignal(
                "bot_generated_names",
                3,
                f"bot-generated names ({first_name} {last_name})",
            )
        )

    if username_mismatches_email(username, email):
        signals.append(
            FakeAccountSignal(
                "username_email_mismatch",
                2,
                "username does not match email local-part",
            )
        )

    if not _email_verified(user):
        signals.append(FakeAccountSignal("unverified_email", 1, "email not verified"))

    if not first_name and not last_name:
        signals.append(FakeAccountSignal("empty_name", 1, "empty first/last name"))

    if not email:
        signals.append(FakeAccountSignal("no_email", 1, "no email on file"))

    return signals


def candidate_queryset(
    *,
    active_only: bool = False,
    usernames: list[str] | None = None,
) -> QuerySet:
    qs = User.objects.filter(is_staff=False, is_superuser=False)
    if active_only:
        qs = qs.filter(is_active=True)
    if usernames:
        qs = qs.filter(username__in=usernames)
    qs = _annotate_engagement(qs).select_related("profile")
    return qs.order_by("date_joined", "pk")


def find_fake_account_candidates(
    *,
    min_score: int = DEFAULT_MIN_SCORE,
    active_only: bool = False,
    usernames: list[str] | None = None,
    require_no_engagement: bool = True,
) -> list[FakeAccountCandidate]:
    """Find accounts that look fake enough to review or clean up.

    By default includes inactive users (already flagged spam). Pass
    ``active_only=True`` to limit to accounts that can still log in.
    """
    candidates: list[FakeAccountCandidate] = []
    for user in candidate_queryset(
        active_only=active_only,
        usernames=usernames,
    ):
        if require_no_engagement and _has_engagement(user):
            continue
        signals = score_user(user)
        score = sum(s.points for s in signals)
        if score < min_score:
            continue
        candidates.append(
            FakeAccountCandidate(
                user=user,
                score=score,
                signals=signals,
                delete_blockers=_delete_blockers(user),
            )
        )
    candidates.sort(key=lambda c: (-c.score, c.user.date_joined, c.user.pk))
    return candidates


def deactivate_users(users: list, *, source: str = "find_fake_accounts") -> int:
    """Set is_active=False and log USER_DEACTIVATED. Returns count changed."""
    changed = 0
    for user in users:
        if not user.is_active:
            continue
        user.is_active = False
        user.save(update_fields=["is_active"])
        record_auth_event(
            event_type=AuthEvent.EventType.USER_DEACTIVATED,
            user=user,
            email=user.email or "",
            source=source,
            reason="fake_account_cleanup",
            metadata={"acted_by": "management_command"},
        )
        changed += 1
    return changed


def delete_users(users: list) -> tuple[int, list[tuple[object, str]]]:
    """Hard-delete users with no PROTECT blockers.

    Returns (deleted_count, [(user, reason), ...] skipped).
    """
    deleted = 0
    skipped: list[tuple[object, str]] = []
    # Re-annotate in case callers pass plain User instances.
    ids = [u.pk for u in users]
    annotated = {
        u.pk: u
        for u in _annotate_engagement(User.objects.filter(pk__in=ids)).select_related(
            "profile"
        )
    }
    for user in users:
        fresh = annotated.get(user.pk)
        if fresh is None:
            skipped.append((user, "not found"))
            continue
        blockers = _delete_blockers(fresh)
        if blockers:
            skipped.append((fresh, ", ".join(blockers)))
            continue
        if _has_engagement(fresh):
            skipped.append((fresh, "has engagement"))
            continue
        fresh.delete()
        deleted += 1
    return deleted, skipped
