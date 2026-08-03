from io import StringIO

import pytest
from django.contrib.auth.models import User
from django.core.management import call_command
from django.utils import timezone

from leaderlodge.accounts.fake_accounts import (
    DEFAULT_MIN_SCORE,
    deactivate_users,
    find_fake_account_candidates,
    names_look_bot_generated,
    score_user,
    username_looks_random,
    username_mismatches_email,
)
from leaderlodge.accounts.models import AuthEvent, UserProfile
from leaderlodge.groups.services import create_group_with_owner


@pytest.mark.parametrize(
    ("username", "expected"),
    [
        ("myylprhhgz", True),
        ("xqzwvtrplk", True),
        ("edsimvhy", True),
        ("david", False),
        ("l.parks", False),
        ("nancy", False),
        ("ab", False),
        ("Myylprhhgz", True),  # case-insensitive; still gibberish
        ("user12345", False),
        ("joseph.berwyn", False),
    ],
)
def test_username_looks_random(username, expected):
    assert username_looks_random(username) is expected


@pytest.mark.parametrize(
    ("first", "last", "expected"),
    [
        ("lqeghxyefp", "lqkluxifvs", True),
        ("izpnwmfutu", "kttgrxlnxl", True),
        ("David", "Manpearl", False),
        ("david", "manpearl", False),  # manpearl vowels too high alone; first short
        ("lqeghxyefp", "Manpearl", False),  # mixed case last
        ("", "lqkluxifvs", False),
    ],
)
def test_names_look_bot_generated(first, last, expected):
    assert names_look_bot_generated(first, last) is expected


@pytest.mark.parametrize(
    ("username", "email", "expected"),
    [
        ("myylprhhgz", "l.parks@tuparks.com", True),
        ("l.parks", "l.parks@tuparks.com", False),
        ("l.parks2", "l.parks@tuparks.com", False),
        ("david", "david@example.com", False),
    ],
)
def test_username_mismatches_email(username, email, expected):
    assert username_mismatches_email(username, email) is expected


def _make_spam_user(**kwargs):
    defaults = {
        "username": "myylprhhgz",
        "email": "l.parks@tuparks.com",
        "password": "unused-pass-123",
    }
    defaults.update(kwargs)
    user = User.objects.create_user(**defaults)
    UserProfile.objects.get_or_create(user=user)
    return user


@pytest.mark.django_db
def test_finds_random_username_with_no_engagement():
    spam = _make_spam_user()
    real = User.objects.create_user(
        username="david",
        email="david@example.com",
        password="test-pass-123",
        first_name="David",
        last_name="Manpearl",
    )
    UserProfile.objects.filter(user=real).update(email_verified_at=timezone.now())
    create_group_with_owner(user=real, name="Dom Club")

    candidates = find_fake_account_candidates()
    usernames = {c.user.username for c in candidates}
    assert spam.username in usernames
    assert real.username not in usernames

    spam_candidate = next(c for c in candidates if c.user.pk == spam.pk)
    assert spam_candidate.score >= 3
    assert spam_candidate.can_delete
    assert any(s.key == "random_username" for s in spam_candidate.signals)
    assert any(s.key == "username_email_mismatch" for s in spam_candidate.signals)


@pytest.mark.django_db
def test_excludes_users_with_group_membership():
    spam = _make_spam_user()
    create_group_with_owner(user=spam, name="Hijacked Club")

    candidates = find_fake_account_candidates()
    assert spam.username not in {c.user.username for c in candidates}


@pytest.mark.django_db
def test_finds_bot_generated_names_even_when_username_matches_email():
    """Production spam often uses email-local username + gibberish names."""
    spam = _make_spam_user(
        username="joseph.berwyn",
        email="joseph.berwyn@blueprintautomation.com",
        first_name="izpnwmfutu",
        last_name="kttgrxlnxl",
    )
    candidates = find_fake_account_candidates()
    match = next(c for c in candidates if c.user.pk == spam.pk)
    assert any(s.key == "bot_generated_names" for s in match.signals)
    assert match.score >= 3


# Captured from production admin (username, email, first, last, email_verified).
# All were inactive; username usually matches email local-part.
_PRODUCTION_SPAM_ROWS = [
    ("kirsten.wesiak", "kirsten.wesiak@homburger.ch", "lgmifxnurg", "qoxqfpopqg", True),
    ("l.parks", "l.parks@tuparks.com", "myylprhhgz", "mkztknrhlx", False),
    ("maalbers", "maalbers@asmodeena.com", "qhhissdiru", "ylfnyemgpn", False),
    ("nycdance", "nycdance@yahoo.com", "kfhfjsizyu", "eiztktlmvy", False),
    ("papo3", "papo3@outlook.com", "iiwjjwmuml", "mkvwfugdhu", False),
    (
        "tjones-charles",
        "tjones-charles@tulaliptribes-nsn.gov",
        "ndmjweeeiz",
        "ousqsqgrdd",
        False,
    ),
]


@pytest.mark.parametrize(
    ("username", "email", "first", "last", "verified"),
    _PRODUCTION_SPAM_ROWS,
)
def test_production_spam_rows_score_as_candidates(
    username, email, first, last, verified
):
    user = User(
        username=username,
        email=email,
        first_name=first,
        last_name=last,
    )
    user.profile = UserProfile(email_verified_at=timezone.now() if verified else None)
    signals = score_user(user)
    assert sum(s.points for s in signals) >= DEFAULT_MIN_SCORE
    assert any(s.key == "bot_generated_names" for s in signals)


@pytest.mark.django_db
def test_inactive_spam_listed_by_default_hidden_with_active_only():
    spam = _make_spam_user(
        username="l.parks",
        email="l.parks@tuparks.com",
        first_name="myylprhhgz",
        last_name="mkztknrhlx",
    )
    spam.is_active = False
    spam.save(update_fields=["is_active"])

    assert spam.username in {c.user.username for c in find_fake_account_candidates()}
    assert spam.username not in {
        c.user.username for c in find_fake_account_candidates(active_only=True)
    }


@pytest.mark.django_db
def test_command_lists_inactive_by_default():
    spam = _make_spam_user(
        username="edsimvhy",
        email="edsimvhy@immenseignite.info",
        first_name="lqeghxyefp",
        last_name="lqkluxifvs",
    )
    spam.is_active = False
    spam.save(update_fields=["is_active"])

    out = StringIO()
    call_command("find_fake_accounts", stdout=out)
    assert "edsimvhy" in out.getvalue()

    out = StringIO()
    call_command("find_fake_accounts", "--active-only", stdout=out)
    assert "edsimvhy" not in out.getvalue()
    assert "No matching fake-account candidates" in out.getvalue()


@pytest.mark.django_db
def test_deactivate_users_logs_auth_event():
    spam = _make_spam_user()
    changed = deactivate_users([spam])
    spam.refresh_from_db()
    assert changed == 1
    assert spam.is_active is False
    assert AuthEvent.objects.filter(
        user=spam,
        event_type=AuthEvent.EventType.USER_DEACTIVATED,
        reason="fake_account_cleanup",
    ).exists()


@pytest.mark.django_db
def test_management_command_report_and_deactivate():
    spam = _make_spam_user()
    out = StringIO()
    call_command("find_fake_accounts", stdout=out)
    report = out.getvalue()
    assert "myylprhhgz" in report
    assert "Report only" in report

    out = StringIO()
    call_command("find_fake_accounts", "--deactivate", stdout=out)
    spam.refresh_from_db()
    assert spam.is_active is False
    assert "Deactivated 1" in out.getvalue()


@pytest.mark.django_db
def test_management_command_delete():
    spam = _make_spam_user()
    pk = spam.pk
    out = StringIO()
    call_command("find_fake_accounts", "--delete", stdout=out)
    assert not User.objects.filter(pk=pk).exists()
    assert "Deleted 1" in out.getvalue()
