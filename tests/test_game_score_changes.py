import pytest
from django.contrib.auth.models import User
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone
from io import StringIO

from leaderlodge.games.models import Game, GameParticipantResult, GameScoreChangeLog
from leaderlodge.games.score_changes import change_game_score, recalculate_game_results
from leaderlodge.groups.services import add_guest_player, create_group_with_owner

Result = GameParticipantResult.Result


@pytest.fixture
def staff_user(db):
    return User.objects.create_user(
        username="staff",
        password="test-pass-123",
        is_staff=True,
    )


@pytest.fixture
def member_user(db, group):
    from leaderlodge.groups.services import add_group_member

    user = User.objects.create_user(username="david", password="test-pass-123")
    add_group_member(group=group, user=user)
    return user


@pytest.fixture
def group(staff_user):
    group = create_group_with_owner(user=staff_user, name="Dom Club")
    add_guest_player(group=group, display_name="Pat")
    add_guest_player(group=group, display_name="Sam")
    return group


@pytest.fixture
def dominos_game(staff_user, group):
    players = list(group.players.order_by("pk"))
    game = Game.objects.create(
        group=group,
        game_type_code="dominos",
        played_on=timezone.localdate(),
        recorded_by=staff_user,
        player_count=2,
    )
    GameParticipantResult.objects.create(
        game=game,
        player=players[0],
        score=30,
        result=Result.WIN,
        placement=0,
    )
    GameParticipantResult.objects.create(
        game=game,
        player=players[1],
        score=20,
        result=Result.PLAYED,
        placement=1,
    )
    return game


@pytest.mark.django_db
def test_change_game_score_updates_results_and_logs(staff_user, dominos_game):
    players = list(dominos_game.group.players.order_by("pk"))
    summary = change_game_score(
        game=dominos_game,
        user=staff_user,
        player=players[1],
        new_score=35,
        notes="Corrected Sam's score from the score sheet.",
    )

    dominos_game.refresh_from_db()
    results = {
        row.player_id: row for row in dominos_game.participant_results.order_by("pk")
    }
    assert results[players[0].pk].result == Result.PLAYED
    assert results[players[1].pk].result == Result.WIN
    assert results[players[1].pk].score == 35
    assert summary.log is not None
    assert GameScoreChangeLog.objects.filter(game=dominos_game).count() == 1
    log = GameScoreChangeLog.objects.get(game=dominos_game)
    assert log.notes == "Corrected Sam's score from the score sheet."
    assert log.changed_by_id == staff_user.pk
    old_sam = next(
        row
        for row in log.old_snapshot["participants"]
        if row["player_id"] == players[1].pk
    )
    new_sam = next(
        row
        for row in log.new_snapshot["participants"]
        if row["player_id"] == players[1].pk
    )
    assert old_sam["score"] == 20
    assert new_sam["score"] == 35
    assert new_sam["result"] == Result.WIN


@pytest.mark.django_db
def test_score_change_does_not_log_unedited_player_result_flip(staff_user, group):
    players = list(group.players.order_by("pk"))
    game = Game.objects.create(
        group=group,
        game_type_code="backgammon",
        played_on=timezone.localdate(),
        recorded_by=staff_user,
        player_count=2,
    )
    GameParticipantResult.objects.create(
        game=game,
        player=players[0],
        score=36,
        result=Result.WIN,
        placement=0,
    )
    GameParticipantResult.objects.create(
        game=game,
        player=players[1],
        score=24,
        result=Result.PLAYED,
        placement=1,
    )

    summary = change_game_score(
        game=game,
        user=staff_user,
        player=players[0],
        new_score=23,
        notes="Corrected Nancy's score.",
    )

    assert summary.log is not None
    assert GameScoreChangeLog.objects.filter(game=game).count() == 1
    log = summary.log
    edited = next(
        row
        for row in log.old_snapshot["participants"]
        if row["player_id"] == players[0].pk
    )
    assert edited["score"] == 36
    updated = next(
        row
        for row in log.new_snapshot["participants"]
        if row["player_id"] == players[0].pk
    )
    assert updated["score"] == 23
    game.refresh_from_db()
    assert game.participant_results.get(player=players[1]).result == Result.WIN


@pytest.mark.django_db
def test_apply_game_edits_location_only(staff_user, dominos_game, group):
    from leaderlodge.games.score_changes import apply_game_edits
    from leaderlodge.groups.locations import resolve_game_location

    new_location = resolve_game_location(group=group, location_name="Clubhouse")

    summary = apply_game_edits(
        game=dominos_game,
        user=staff_user,
        notes="Wrong room was selected when recording.",
        score_updates={},
        new_location=new_location,
    )

    dominos_game.refresh_from_db()
    assert dominos_game.location_id == new_location.pk
    assert summary.log is not None
    log = summary.log
    assert log.old_snapshot["location"] is None
    assert log.new_snapshot["location"]["name"] == "Clubhouse"
    assert log.changed_by_id == staff_user.pk
    assert log.old_snapshot["participants"][0]["score"] == 30
    assert log.old_snapshot["participants"][0]["result"] == Result.WIN


@pytest.mark.django_db
def test_game_edit_location_only(client, staff_user, dominos_game, group):
    from leaderlodge.groups.locations import resolve_game_location

    resolve_game_location(group=group, location_name="Clubhouse")
    client.force_login(staff_user)
    participants = list(dominos_game.participant_results.order_by("pk"))
    url = reverse("games:edit_game", kwargs={"pk": dominos_game.pk})
    response = client.post(
        url,
        {
            "played_on": dominos_game.played_on.isoformat(),
            "location_name": "Clubhouse",
            f"score_{participants[0].pk}": participants[0].score,
            f"score_{participants[1].pk}": participants[1].score,
            "notes": "Recorded in the wrong room.",
        },
    )
    assert response.status_code == 302
    dominos_game.refresh_from_db()
    assert dominos_game.location.name == "Clubhouse"
    assert GameScoreChangeLog.objects.filter(game=dominos_game).count() == 1
    log = GameScoreChangeLog.objects.get(game=dominos_game)
    assert log.new_snapshot["location"]["name"] == "Clubhouse"


@pytest.mark.django_db
def test_recalculate_game_results_without_score_change(staff_user, dominos_game):
    summary = recalculate_game_results(
        game=dominos_game,
        user=staff_user,
        notes="Registry rules refresh.",
    )
    assert summary.log is None
    assert GameScoreChangeLog.objects.count() == 0


@pytest.mark.django_db
def test_change_game_score_command_calls_recalculate(staff_user, dominos_game):
    players = list(dominos_game.group.players.order_by("pk"))
    stdout = StringIO()
    call_command(
        "change_game_score",
        game=dominos_game.pk,
        player=str(players[1].pk),
        score=35,
        changed_by=staff_user.username,
        notes="Fixed typo in spreadsheet import.",
        stdout=stdout,
    )
    dominos_game.refresh_from_db()
    winner = dominos_game.participant_results.get(player=players[1])
    assert winner.score == 35
    assert winner.result == Result.WIN
    assert GameScoreChangeLog.objects.filter(game=dominos_game).count() == 1


@pytest.mark.django_db
def test_recalculate_game_results_command(staff_user, dominos_game):
    participants = list(dominos_game.participant_results.order_by("pk"))
    participants[0].result = Result.PLAYED
    participants[1].result = Result.WIN
    GameParticipantResult.objects.bulk_update(participants, ["result"])

    stdout = StringIO()
    call_command(
        "recalculate_game_results",
        game=dominos_game.pk,
        changed_by=staff_user.username,
        notes="Fix results after manual admin edit.",
        stdout=stdout,
    )

    dominos_game.refresh_from_db()
    results = list(dominos_game.participant_results.order_by("pk"))
    assert results[0].result == Result.WIN
    assert results[1].result == Result.PLAYED
    assert GameScoreChangeLog.objects.filter(game=dominos_game).count() == 1


@pytest.mark.django_db
def test_game_edit_includes_location_autocomplete(client, staff_user, dominos_game):
    client.force_login(staff_user)
    response = client.get(reverse("games:edit_game", kwargs={"pk": dominos_game.pk}))
    content = response.content.decode()
    assert response.status_code == 200
    assert 'data-location-autocomplete="true"' in content
    assert f'data-location-group-id="{dominos_game.group.pk}"' in content
    assert "location_autocomplete.js" in content
    assert "/groups/0/locations/" in content


@pytest.mark.django_db
def test_game_detail_shows_edit_game_for_staff(client, staff_user, dominos_game):
    client.force_login(staff_user)
    response = client.get(reverse("games:detail", kwargs={"pk": dominos_game.pk}))
    content = response.content.decode()
    assert response.status_code == 200
    assert "bi-pencil-square" in content
    assert reverse("games:edit_game", kwargs={"pk": dominos_game.pk}) in content


@pytest.mark.django_db
def test_game_detail_hides_edit_game_for_member(client, member_user, dominos_game):
    client.force_login(member_user)
    response = client.get(reverse("games:detail", kwargs={"pk": dominos_game.pk}))
    content = response.content.decode()
    assert response.status_code == 200
    assert "bi-pencil-square" not in content


@pytest.mark.django_db
def test_game_edit_updates_game(client, staff_user, dominos_game):
    client.force_login(staff_user)
    participants = list(dominos_game.participant_results.order_by("pk"))
    url = reverse("games:edit_game", kwargs={"pk": dominos_game.pk})
    response = client.post(
        url,
        {
            "played_on": dominos_game.played_on.isoformat(),
            f"score_{participants[0].pk}": participants[0].score,
            f"score_{participants[1].pk}": 35,
            "notes": "Sam actually won this one.",
        },
    )
    assert response.status_code == 302
    dominos_game.refresh_from_db()
    winner = dominos_game.participant_results.get(player=participants[1].player)
    assert winner.score == 35
    assert winner.result == Result.WIN
    assert GameScoreChangeLog.objects.filter(game=dominos_game).count() == 1


@pytest.mark.django_db
def test_game_edit_requires_notes(client, staff_user, dominos_game):
    client.force_login(staff_user)
    participants = list(dominos_game.participant_results.order_by("pk"))
    url = reverse("games:edit_game", kwargs={"pk": dominos_game.pk})
    response = client.post(
        url,
        {
            "played_on": dominos_game.played_on.isoformat(),
            f"score_{participants[0].pk}": participants[0].score,
            f"score_{participants[1].pk}": 35,
            "notes": "   ",
        },
    )
    assert response.status_code == 200
    form = response.context["form"]
    assert "notes" in form.errors


@pytest.mark.django_db
def test_game_edit_is_staff_only(client, member_user, dominos_game):
    client.force_login(member_user)
    url = reverse("games:edit_game", kwargs={"pk": dominos_game.pk})
    response = client.get(url)
    assert response.status_code == 404


@pytest.mark.django_db
def test_game_edit_played_on_only(staff_user, dominos_game):
    from datetime import timedelta

    from leaderlodge.games.score_changes import apply_game_edits

    new_date = dominos_game.played_on - timedelta(days=1)
    summary = apply_game_edits(
        game=dominos_game,
        user=staff_user,
        notes="Wrong day on the score sheet.",
        score_updates={},
        new_played_on=new_date,
    )

    dominos_game.refresh_from_db()
    assert dominos_game.played_on == new_date
    assert summary.log is not None
    assert (
        summary.log.old_snapshot["played_on"]
        == (new_date + timedelta(days=1)).isoformat()
    )
    assert summary.log.new_snapshot["played_on"] == new_date.isoformat()


@pytest.mark.django_db
def test_game_edit_played_on_via_form(client, staff_user, dominos_game):
    from datetime import timedelta

    client.force_login(staff_user)
    participants = list(dominos_game.participant_results.order_by("pk"))
    new_date = dominos_game.played_on - timedelta(days=2)
    url = reverse("games:edit_game", kwargs={"pk": dominos_game.pk})
    response = client.post(
        url,
        {
            "played_on": new_date.isoformat(),
            f"score_{participants[0].pk}": participants[0].score,
            f"score_{participants[1].pk}": participants[1].score,
            "notes": "Recorded on the wrong calendar day.",
        },
    )
    assert response.status_code == 302
    dominos_game.refresh_from_db()
    assert dominos_game.played_on == new_date
    log = GameScoreChangeLog.objects.get(game=dominos_game)
    assert log.new_snapshot["played_on"] == new_date.isoformat()
