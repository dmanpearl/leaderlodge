from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest
from django.contrib.auth.models import User
from django.core.management import call_command
from io import StringIO
from openpyxl import Workbook

from leaderlodge.games.importing.scorekeeper import parse_scorekeeper_workbook
from leaderlodge.games.importing.service import import_scorekeeper_file
from leaderlodge.games.models import Game
from leaderlodge.groups.models import GroupPlayer
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
