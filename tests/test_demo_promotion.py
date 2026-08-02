from io import StringIO

import pytest
from django.contrib.auth.models import User
from django.core.management import call_command
from django.utils import timezone

from leaderlodge.games.models import Game, GameParticipantResult
from leaderlodge.games.services import ParticipantInput, record_game
from leaderlodge.groups import demo_promotion
from leaderlodge.groups.demo_promotion import (
    promote_games,
    purge_promoted_games,
)
from leaderlodge.groups.location_geo import location_geo
from leaderlodge.groups.locations import resolve_game_location
from leaderlodge.groups.services import add_guest_player, create_group_with_owner
from leaderlodge.groups.teams import resolve_side_player


@pytest.fixture
def admin(db):
    return User.objects.create_user(username="admin", password="test-pass-123")


@pytest.fixture
def source_group(admin):
    return create_group_with_owner(user=admin, name="Source Group")


@pytest.fixture
def dest_group(admin):
    return create_group_with_owner(user=admin, name="Dest Group")


@pytest.fixture(autouse=True)
def name_map(monkeypatch):
    mapping = {"Nancy": "Amelia", "David": "Hudson", "Karen": "Layla"}
    monkeypatch.setattr(demo_promotion, "PLAYER_NAME_MAP", mapping)
    return mapping


@pytest.fixture(autouse=True)
def location_map(monkeypatch):
    mapping = {"Nancy's House": "Amelia's House"}
    monkeypatch.setattr(demo_promotion, "LOCATION_NAME_MAP", mapping)
    return mapping


def _record(group, admin, home, away, *, location=None, played_on=None):
    return record_game(
        user=admin,
        group=group,
        game_type_code="dominos",
        played_on=played_on or timezone.localdate(),
        participants=[
            ParticipantInput(
                player=home,
                score=30,
                result=GameParticipantResult.Result.WIN,
                placement=0,
            ),
            ParticipantInput(
                player=away,
                score=10,
                result=GameParticipantResult.Result.PLAYED,
                placement=1,
            ),
        ],
        location=location,
    )


@pytest.mark.django_db
def test_promote_remaps_solo_players_and_creates_guest_in_dest(
    source_group, dest_group, admin
):
    nancy = add_guest_player(group=source_group, display_name="Nancy")
    david = add_guest_player(group=source_group, display_name="David")
    _record(source_group, admin, nancy, david)

    summary = promote_games(
        source_group=source_group, dest_group=dest_group, recorded_by=admin
    )

    assert summary.created == 1
    assert summary.skipped_unmapped_player == 0
    dest_game = Game.objects.get(group=dest_group)
    labels = {r.player.display_label for r in dest_game.participant_results.all()}
    assert labels == {"Amelia", "Hudson"}

    amelia = dest_group.players.get(display_name="Amelia")
    assert amelia.linked_user_id is None
    assert amelia.is_team is False


@pytest.mark.django_db
def test_promote_skips_and_reports_unmapped_player(source_group, dest_group, admin):
    nancy = add_guest_player(group=source_group, display_name="Nancy")
    mystery = add_guest_player(group=source_group, display_name="Mystery Guest")
    _record(source_group, admin, nancy, mystery)

    summary = promote_games(
        source_group=source_group, dest_group=dest_group, recorded_by=admin
    )

    assert summary.created == 0
    assert summary.skipped_unmapped_player == 1
    assert summary.unmapped_player_names == {"Mystery Guest"}
    assert not Game.objects.filter(group=dest_group).exists()


@pytest.mark.django_db
def test_promote_maps_team_via_members(source_group, dest_group, admin):
    nancy = add_guest_player(group=source_group, display_name="Nancy")
    david = add_guest_player(group=source_group, display_name="David")
    karen = add_guest_player(group=source_group, display_name="Karen")
    team = resolve_side_player(group=source_group, members=[nancy, david])

    _record(source_group, admin, team, karen)

    summary = promote_games(
        source_group=source_group, dest_group=dest_group, recorded_by=admin
    )

    assert summary.created == 1
    dest_game = Game.objects.get(group=dest_group)
    labels = {r.player.display_label for r in dest_game.participant_results.all()}
    assert labels == {"Amelia+Hudson", "Layla"}

    dest_team = dest_group.players.get(display_name="Amelia+Hudson")
    assert dest_team.is_team is True


@pytest.mark.django_db
def test_promote_blurs_geo_for_remapped_location_and_keeps_business_geo_exact(
    source_group, dest_group, admin
):
    nancy = add_guest_player(group=source_group, display_name="Nancy")
    david = add_guest_player(group=source_group, display_name="David")

    house = resolve_game_location(
        group=source_group,
        location_name="Nancy's House",
        geo=location_geo(lat=34.123456, lon=-118.654321),
    )
    cafe = resolve_game_location(
        group=source_group,
        location_name="Joe's Cafe",
        geo=location_geo(lat=40.111111, lon=-74.222222, city="NYC"),
    )

    _record(source_group, admin, nancy, david, location=house)
    _record(
        source_group,
        admin,
        nancy,
        david,
        location=cafe,
        played_on=timezone.localdate() - timezone.timedelta(days=1),
    )

    promote_games(source_group=source_group, dest_group=dest_group, recorded_by=admin)

    dest_group.refresh_from_db()
    dest_house = dest_group.location_library.locations.get(name="Amelia's House")
    assert dest_house.lat == 34.12
    assert dest_house.lon == -118.65

    dest_cafe = dest_group.location_library.locations.get(name="Joe's Cafe")
    assert dest_cafe.lat == 40.111111
    assert dest_cafe.city == "NYC"


@pytest.mark.django_db
def test_promote_dry_run_writes_nothing(source_group, dest_group, admin):
    nancy = add_guest_player(group=source_group, display_name="Nancy")
    david = add_guest_player(group=source_group, display_name="David")
    _record(source_group, admin, nancy, david)
    baseline_player_count = dest_group.players.count()

    summary = promote_games(
        source_group=source_group,
        dest_group=dest_group,
        recorded_by=admin,
        dry_run=True,
    )

    assert summary.created == 1
    assert not Game.objects.filter(group=dest_group).exists()
    assert dest_group.players.count() == baseline_player_count


@pytest.mark.django_db
def test_promote_is_idempotent_on_rerun(source_group, dest_group, admin):
    nancy = add_guest_player(group=source_group, display_name="Nancy")
    david = add_guest_player(group=source_group, display_name="David")
    _record(source_group, admin, nancy, david)

    first = promote_games(
        source_group=source_group, dest_group=dest_group, recorded_by=admin
    )
    second = promote_games(
        source_group=source_group, dest_group=dest_group, recorded_by=admin
    )

    assert first.created == 1
    assert second.created == 0
    assert second.already_promoted == 1
    assert Game.objects.filter(group=dest_group).count() == 1


@pytest.mark.django_db
def test_promote_only_promotes_matching_game_type(source_group, dest_group, admin):
    nancy = add_guest_player(group=source_group, display_name="Nancy")
    david = add_guest_player(group=source_group, display_name="David")
    _record(source_group, admin, nancy, david)
    record_game(
        user=admin,
        group=source_group,
        game_type_code="backgammon",
        played_on=timezone.localdate(),
        participants=[
            ParticipantInput(
                player=nancy,
                score=1,
                result=GameParticipantResult.Result.WIN,
                placement=0,
            ),
            ParticipantInput(
                player=david,
                score=0,
                result=GameParticipantResult.Result.PLAYED,
                placement=1,
            ),
        ],
    )

    summary = promote_games(
        source_group=source_group,
        dest_group=dest_group,
        recorded_by=admin,
        game_type_code="dominos",
    )

    assert summary.total_source_games == 1
    assert summary.created == 1
    assert Game.objects.get(group=dest_group).game_type_code == "dominos"


@pytest.mark.django_db
def test_purge_promoted_games_only_removes_promoted_games(
    source_group, dest_group, admin
):
    nancy = add_guest_player(group=source_group, display_name="Nancy")
    david = add_guest_player(group=source_group, display_name="David")
    _record(source_group, admin, nancy, david)
    promote_games(source_group=source_group, dest_group=dest_group, recorded_by=admin)

    amelia = dest_group.players.get(display_name="Amelia")
    hudson = dest_group.players.get(display_name="Hudson")
    _record(
        dest_group,
        admin,
        amelia,
        hudson,
        played_on=timezone.localdate() - timezone.timedelta(days=5),
    )
    assert Game.objects.filter(group=dest_group).count() == 2

    purged = purge_promoted_games(source_group=source_group, dest_group=dest_group)

    assert purged == 1
    assert Game.objects.filter(group=dest_group).count() == 1


@pytest.mark.django_db
def test_promote_games_command_runs_and_reports_summary(
    source_group, dest_group, admin
):
    nancy = add_guest_player(group=source_group, display_name="Nancy")
    david = add_guest_player(group=source_group, display_name="David")
    _record(source_group, admin, nancy, david)

    out = StringIO()
    call_command(
        "promote_games",
        "--source-group",
        str(source_group.pk),
        "--dest-group",
        str(dest_group.pk),
        stdout=out,
    )

    output = out.getvalue()
    assert "Created:           1" in output
    assert Game.objects.filter(group=dest_group).count() == 1
