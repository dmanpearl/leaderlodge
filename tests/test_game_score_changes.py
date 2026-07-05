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
    assert len(summary.logs) == 1
    assert GameScoreChangeLog.objects.filter(game=dominos_game).count() == 1
    log = GameScoreChangeLog.objects.filter(player=players[1]).get()
    assert log.notes == "Corrected Sam's score from the score sheet."
    assert log.changed_by_id == staff_user.pk
    assert log.change_type == GameScoreChangeLog.ChangeType.SCORE_CHANGE


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

    assert len(summary.logs) == 1
    log = summary.logs[0]
    assert log.player_id == players[0].pk
    assert log.old_score == 36
    assert log.new_score == 23
    game.refresh_from_db()
    assert game.participant_results.get(player=players[1]).result == Result.WIN


@pytest.mark.django_db
def test_recalculate_game_results_without_score_change(staff_user, dominos_game):
    summary = recalculate_game_results(
        game=dominos_game,
        user=staff_user,
        notes="Registry rules refresh.",
    )
    assert summary.logs == []
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
    assert GameScoreChangeLog.objects.filter(game=dominos_game).exists()


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
    assert GameScoreChangeLog.objects.filter(
        game=dominos_game,
        change_type=GameScoreChangeLog.ChangeType.RECALCULATE,
    ).exists()


@pytest.mark.django_db
def test_game_detail_shows_edit_scores_for_staff(client, staff_user, dominos_game):
    client.force_login(staff_user)
    response = client.get(reverse("games:detail", kwargs={"pk": dominos_game.pk}))
    content = response.content.decode()
    assert response.status_code == 200
    assert "bi-pencil-square" in content
    assert reverse("games:edit_scores", kwargs={"pk": dominos_game.pk}) in content


@pytest.mark.django_db
def test_game_detail_hides_edit_scores_for_member(client, member_user, dominos_game):
    client.force_login(member_user)
    response = client.get(reverse("games:detail", kwargs={"pk": dominos_game.pk}))
    content = response.content.decode()
    assert response.status_code == 200
    assert "bi-pencil-square" not in content


@pytest.mark.django_db
def test_game_edit_scores_updates_game(client, staff_user, dominos_game):
    client.force_login(staff_user)
    participants = list(dominos_game.participant_results.order_by("pk"))
    url = reverse("games:edit_scores", kwargs={"pk": dominos_game.pk})
    response = client.post(
        url,
        {
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
    assert GameScoreChangeLog.objects.filter(game=dominos_game).exists()


@pytest.mark.django_db
def test_game_edit_scores_requires_notes(client, staff_user, dominos_game):
    client.force_login(staff_user)
    participants = list(dominos_game.participant_results.order_by("pk"))
    url = reverse("games:edit_scores", kwargs={"pk": dominos_game.pk})
    response = client.post(
        url,
        {
            f"score_{participants[0].pk}": participants[0].score,
            f"score_{participants[1].pk}": 35,
            "notes": "   ",
        },
    )
    assert response.status_code == 200
    form = response.context["form"]
    assert "notes" in form.errors


@pytest.mark.django_db
def test_game_edit_scores_is_staff_only(client, member_user, dominos_game):
    client.force_login(member_user)
    url = reverse("games:edit_scores", kwargs={"pk": dominos_game.pk})
    response = client.get(url)
    assert response.status_code == 404
