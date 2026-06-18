from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest
from django.contrib.auth.models import User
from django.core.management import call_command
from io import StringIO
from openpyxl import Workbook

from leaderlodge.games.importing.progressiverummy import parse_progressiverummy_workbook
from leaderlodge.games.importing.scorekeeper import parse_scorekeeper_workbook
from leaderlodge.games.importing.service import (
    import_progressiverummy_file,
    import_scorekeeper_file,
)
from leaderlodge.games.models import Game
from leaderlodge.groups.models import GroupMembership, GroupPlayer
from leaderlodge.groups.names import format_user_display_name
from leaderlodge.groups.services import (
    add_guest_player,
    create_group_with_owner,
    resolve_seed_player,
)


@pytest.fixture
def user(db):
    return User.objects.create_user(
        username="david",
        password="test-pass-123",
        first_name="David",
        last_name="Pearl",
    )


@pytest.fixture
def group(user):
    return create_group_with_owner(user=user, name="Family")


def _write_scorekeeper(path: Path, rows: list[tuple]) -> None:
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "ScoreKeeper"
    worksheet.append(
        ("Date", "Nancy", "David", "Where", "Nancy", "David", "Diff")
    )
    worksheet.append(("Totals", 0, 0, None, 0, 0, None))
    for row in rows:
        worksheet.append(row)
    workbook.save(path)


@pytest.fixture
def sample_spreadsheet(tmp_path):
    path = tmp_path / "dominos_seed_test.xlsx"
    _write_scorekeeper(
        path,
        [
            (datetime(2026, 3, 8), 25, 30, "Sally"),
            (datetime(2026, 3, 9), 30, 25, None),
        ],
    )
    return path


def test_format_user_display_name():
    user = User(
        username="david",
        first_name="David",
        last_name="Pearl",
    )
    assert format_user_display_name(user) == "David P."

    user = User(username="david", first_name="David")
    assert format_user_display_name(user) == "David"

    user = User(username="david")
    assert format_user_display_name(user) == "david"


@pytest.mark.django_db
def test_resolve_seed_player_matches_linked_username(group, user):
    player = resolve_seed_player(group=group, seed_name="david")
    assert player.linked_user_id == user.pk


@pytest.mark.django_db
def test_resolve_seed_player_matches_linked_first_name(group, user):
    player = resolve_seed_player(group=group, seed_name="David")
    assert player.linked_user_id == user.pk


@pytest.mark.django_db
def test_resolve_seed_player_matches_existing_guest(group):
    guest = add_guest_player(group=group, display_name="Nancy")
    player = resolve_seed_player(group=group, seed_name="Nancy")
    assert player.pk == guest.pk


@pytest.mark.django_db
def test_resolve_seed_player_matches_inactive_guest(group):
    guest = add_guest_player(group=group, display_name="Nancy")
    guest.is_active = False
    guest.save(update_fields=["is_active"])

    player = resolve_seed_player(group=group, seed_name="Nancy")
    assert player.pk == guest.pk


@pytest.mark.django_db
def test_resolve_seed_player_matches_inactive_linked_first_name(group, user):
    nancy_user = User.objects.create_user(
        username="nmanpearl",
        password="test-pass-123",
        first_name="Nancy",
        last_name="Pearl",
    )
    player = GroupPlayer.objects.create(
        group=group,
        display_name="Nancy P.",
        linked_user=nancy_user,
        is_active=False,
    )

    resolved = resolve_seed_player(group=group, seed_name="Nancy")
    assert resolved.pk == player.pk
    assert resolved.linked_user_id == nancy_user.pk


@pytest.mark.django_db
def test_resolve_seed_player_creates_player_for_group_member_first_name(group, user):
    nancy_user = User.objects.create_user(
        username="nmanpearl",
        password="test-pass-123",
        first_name="Nancy",
    )
    GroupMembership.objects.create(
        group=group,
        user=nancy_user,
        role=GroupMembership.Role.MEMBER,
    )

    player = resolve_seed_player(group=group, seed_name="Nancy")
    assert player.linked_user_id == nancy_user.pk
    assert player.display_name == "Nancy"


@pytest.mark.django_db
def test_resolve_seed_player_prefers_linked_user_over_guest_display_name(group, user):
    add_guest_player(group=group, display_name="Nancy")
    nancy_user = User.objects.create_user(
        username="nmanpearl",
        password="test-pass-123",
        first_name="Nancy",
    )
    linked = GroupPlayer.objects.create(
        group=group,
        display_name="Nancy P.",
        linked_user=nancy_user,
    )

    player = resolve_seed_player(group=group, seed_name="Nancy")
    assert player.pk == linked.pk


@pytest.mark.django_db
def test_import_scorekeeper_file_uses_linked_nancy_player(group, user, sample_spreadsheet):
    nancy_user = User.objects.create_user(
        username="nmanpearl",
        password="test-pass-123",
        first_name="Nancy",
    )
    nancy_player = GroupPlayer.objects.create(
        group=group,
        display_name="Nancy",
        linked_user=nancy_user,
    )

    summary = import_scorekeeper_file(
        path=sample_spreadsheet,
        group=group,
        game_type_code="dominos",
        recorded_by=user,
    )

    assert summary.created == 2
    assert GroupPlayer.objects.filter(group=group, display_name="Nancy").count() == 1
    games = Game.objects.filter(group=group).prefetch_related(
        "participant_results__player"
    )
    for game in games:
        nancy_participant = game.participant_results.get(player__linked_user=nancy_user)
        assert nancy_participant.player_id == nancy_player.pk


@pytest.mark.django_db
def test_resolve_seed_player_creates_guest(group):
    player = resolve_seed_player(group=group, seed_name="Nancy")
    assert player.display_name == "Nancy"
    assert player.linked_user is None


def test_parse_scorekeeper_workbook(sample_spreadsheet):
    rows = parse_scorekeeper_workbook(sample_spreadsheet)
    assert len(rows) == 2
    assert rows[0].played_on.isoformat() == "2026-03-08"
    assert rows[0].nancy_score == 25
    assert rows[0].david_score == 30
    assert rows[0].location_name == "Sally"
    assert rows[1].location_name == ""


@pytest.mark.django_db
def test_import_scorekeeper_file(group, user, sample_spreadsheet):
    summary = import_scorekeeper_file(
        path=sample_spreadsheet,
        group=group,
        game_type_code="dominos",
        recorded_by=user,
    )

    assert summary.parsed == 2
    assert summary.created == 2
    assert summary.skipped == 0
    assert Game.objects.filter(group=group).count() == 2
    assert GroupPlayer.objects.filter(group=group, display_name="Nancy").exists()


@pytest.mark.django_db
def test_import_scorekeeper_file_is_idempotent(group, user, sample_spreadsheet):
    import_scorekeeper_file(
        path=sample_spreadsheet,
        group=group,
        game_type_code="dominos",
        recorded_by=user,
    )
    summary = import_scorekeeper_file(
        path=sample_spreadsheet,
        group=group,
        game_type_code="dominos",
        recorded_by=user,
    )

    assert summary.created == 0
    assert summary.skipped == 2
    assert Game.objects.filter(group=group).count() == 2


@pytest.mark.django_db
def test_import_games_command(group, user, sample_spreadsheet):
    stdout = StringIO()
    call_command(
        "import_games",
        str(sample_spreadsheet),
        "--group",
        str(group.pk),
        "--game-type",
        "dominos",
        stdout=stdout,
    )

    output = stdout.getvalue()
    assert "Created: 2" in output
    assert Game.objects.filter(group=group, import_source="dominos_seed_test").count() == 2


@pytest.mark.django_db
def test_import_backgammon_after_dominos(group, user, sample_spreadsheet, tmp_path):
    """Second scorekeeper import reuses Nancy created by the first."""
    backgammon_path = tmp_path / "backgammon_seed_test.xlsx"
    _write_scorekeeper(
        backgammon_path,
        [
            (datetime(2026, 4, 1), 1, 0, "Home"),
        ],
    )

    import_scorekeeper_file(
        path=sample_spreadsheet,
        group=group,
        game_type_code="dominos",
        recorded_by=user,
    )
    assert GroupPlayer.objects.filter(group=group, display_name="Nancy").count() == 1

    summary = import_scorekeeper_file(
        path=backgammon_path,
        group=group,
        game_type_code="backgammon",
        recorded_by=user,
    )

    assert summary.created == 1
    assert GroupPlayer.objects.filter(group=group, display_name="Nancy").count() == 1


@pytest.mark.django_db
def test_resolve_seed_player_reuses_existing_after_integrity_error(group):
    add_guest_player(group=group, display_name="Nancy")
    player = resolve_seed_player(group=group, seed_name="Nancy")
    assert player.display_name == "Nancy"
    assert GroupPlayer.objects.filter(group=group, display_name="Nancy").count() == 1


@pytest.mark.django_db
def test_import_real_backgammon_seed(group, user):
    path = Path("data/seeds/backgammon/backgammon_seed_2026-06-16.xlsx")
    if not path.is_file():
        pytest.skip("Seed file not present")

    summary = import_scorekeeper_file(
        path=path,
        group=group,
        game_type_code="backgammon",
        recorded_by=user,
    )

    assert summary.parsed == 5
    assert summary.created == 5
    assert Game.objects.filter(
        group=group,
        game_type_code="backgammon",
        import_source="backgammon_seed_2026-06-16",
    ).count() == 5


def _write_progressiverummy(path: Path, rows: list[tuple]) -> None:
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Raw Games"
    worksheet.append(
        (
            "Date",
            "Where",
            "Half",
            "aa",
            "Nancy",
            "David",
            "Pat",
            "Min",
            "Max",
            "Winner",
            "Loser",
            "Players",
        )
    )
    for row in rows:
        worksheet.append(row)
    workbook.save(path)


@pytest.fixture
def progressiverummy_spreadsheet(tmp_path):
    path = tmp_path / "progressiverummy_seed_test.xlsx"
    _write_progressiverummy(
        path,
        [
            (datetime(2026, 3, 8), "Sally", "Yes", "skip", 10, 20, 30, 10, 30, "Nancy", "Pat", 3),
            (datetime(2026, 3, 9), "<?>", None, None, 5, 15, 25, 5, 25, "Nancy", "Pat", 3),
            ("<?>", "Kitchen", None, None, 8, 18, 28, 8, 28, "Nancy", "Pat", 3),
        ],
    )
    return path


def test_parse_progressiverummy_workbook(progressiverummy_spreadsheet):
    rows = parse_progressiverummy_workbook(progressiverummy_spreadsheet)
    assert len(rows) == 3

    assert rows[0].played_on.isoformat() == "2026-03-08"
    assert rows[0].location_name == "Sally"
    assert rows[0].is_half is True
    assert [ps.name for ps in rows[0].player_scores] == ["Nancy", "David", "Pat"]
    assert rows[0].metadata["Winner"] == "Nancy"

    assert rows[1].location_name == ""
    assert rows[1].is_half is False

    assert rows[2].played_on.isoformat() == "2026-03-07"
    assert rows[2].location_name == "Kitchen"


@pytest.mark.django_db
def test_import_progressiverummy_file(group, user, progressiverummy_spreadsheet):
    summary = import_progressiverummy_file(
        path=progressiverummy_spreadsheet,
        group=group,
        recorded_by=user,
    )

    assert summary.parsed == 3
    assert summary.created == 3
    assert summary.skipped == 0

    games = Game.objects.filter(group=group, game_type_code="progressiverummy").order_by("pk")
    assert games.count() == 3
    assert games[0].half_weight == 2
    assert games[1].half_weight == 1
    assert games[2].half_weight == 1
    assert GroupPlayer.objects.filter(group=group, display_name="Pat").exists()


@pytest.mark.django_db
def test_import_progressiverummy_file_is_idempotent(group, user, progressiverummy_spreadsheet):
    import_progressiverummy_file(
        path=progressiverummy_spreadsheet,
        group=group,
        recorded_by=user,
    )
    summary = import_progressiverummy_file(
        path=progressiverummy_spreadsheet,
        group=group,
        recorded_by=user,
    )

    assert summary.created == 0
    assert summary.skipped == 3


@pytest.mark.django_db
def test_import_progressiverummy_command(group, user, progressiverummy_spreadsheet):
    stdout = StringIO()
    call_command(
        "import_games",
        str(progressiverummy_spreadsheet),
        "--group",
        str(group.pk),
        "--game-type",
        "progressiverummy",
        stdout=stdout,
    )

    output = stdout.getvalue()
    assert "Created: 3" in output
    assert Game.objects.filter(
        group=group,
        import_source="progressiverummy_seed_test",
    ).count() == 3


@pytest.mark.django_db
def test_import_real_progressiverummy_seed(group, user):
    path = Path("data/seeds/progressiverummy/progressiverummy_seed_2026-06-16.xlsx")
    if not path.is_file():
        pytest.skip("Seed file not present")

    summary = import_progressiverummy_file(
        path=path,
        group=group,
        recorded_by=user,
    )

    assert summary.parsed > 500
    assert summary.created > 500
    assert summary.skipped == summary.parsed - summary.created
    half_games = Game.objects.filter(
        group=group,
        game_type_code="progressiverummy",
        half_weight=2,
    ).count()
    assert half_games > 50
