import pytest
from django.contrib.auth.models import User
from django.forms import inlineformset_factory
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from leaderlodge.games.admin import GameParticipantResultInlineFormSet
from leaderlodge.games.models import Game, GameParticipantResult
from leaderlodge.groups.services import add_guest_player, create_group_with_owner

Result = GameParticipantResult.Result


@pytest.fixture
def admin_user(db):
    return User.objects.create_superuser(
        username="admin",
        email="admin@example.com",
        password="test-pass-123",
    )


@pytest.fixture
def group(admin_user):
    group = create_group_with_owner(user=admin_user, name="Admin Club")
    add_guest_player(group=group, display_name="Alex")
    add_guest_player(group=group, display_name="Blake")
    return group


@pytest.fixture
def backgammon_game(admin_user, group):
    players = list(group.players.order_by("pk"))
    game = Game.objects.create(
        group=group,
        game_type_code="backgammon",
        played_on=timezone.localdate(),
        recorded_by=admin_user,
        player_count=2,
    )
    GameParticipantResult.objects.create(
        game=game,
        player=players[0],
        score=5,
        result=Result.WIN,
        placement=0,
    )
    GameParticipantResult.objects.create(
        game=game,
        player=players[1],
        score=0,
        result=Result.LOSS,
        placement=1,
    )
    return game


def _inline_formset(*, game, data):
    factory = inlineformset_factory(
        Game,
        GameParticipantResult,
        formset=GameParticipantResultInlineFormSet,
        fields=("player", "score", "result", "placement"),
        extra=0,
    )
    queryset = game.participant_results.order_by("pk")
    prefix = "results"
    if data is None:
        formset = factory(instance=game, queryset=queryset, prefix=prefix)
        data = formset.management_form.initial
        for index, participant in enumerate(queryset):
            data.update(
                {
                    f"{prefix}-{index}-id": participant.pk,
                    f"{prefix}-{index}-player": participant.player_id,
                    f"{prefix}-{index}-score": participant.score,
                    f"{prefix}-{index}-result": participant.result,
                    f"{prefix}-{index}-placement": participant.placement,
                }
            )
    return factory(instance=game, data=data, queryset=queryset, prefix=prefix)


@pytest.mark.django_db
def test_game_clean_ignores_stale_participant_results(backgammon_game):
    backgammon_game.clean()


@pytest.mark.django_db
def test_game_admin_formset_accepts_backgammon_win_and_played(backgammon_game):
    participants = list(backgammon_game.participant_results.order_by("pk"))
    data = {
        "results-TOTAL_FORMS": "2",
        "results-INITIAL_FORMS": "2",
        "results-MIN_NUM_FORMS": "0",
        "results-MAX_NUM_FORMS": "1000",
        f"results-0-id": participants[0].pk,
        f"results-0-player": participants[0].player_id,
        f"results-0-score": participants[0].score,
        f"results-0-result": Result.WIN,
        f"results-0-placement": participants[0].placement,
        f"results-1-id": participants[1].pk,
        f"results-1-player": participants[1].player_id,
        f"results-1-score": participants[1].score,
        f"results-1-result": Result.PLAYED,
        f"results-1-placement": participants[1].placement,
    }
    formset = _inline_formset(game=backgammon_game, data=data)
    assert formset.is_valid(), formset.errors


@pytest.mark.django_db
def test_game_admin_formset_normalizes_loss_to_played_for_backgammon(backgammon_game):
    participants = list(backgammon_game.participant_results.order_by("pk"))
    data = {
        "results-TOTAL_FORMS": "2",
        "results-INITIAL_FORMS": "2",
        "results-MIN_NUM_FORMS": "0",
        "results-MAX_NUM_FORMS": "1000",
        f"results-0-id": participants[0].pk,
        f"results-0-player": participants[0].player_id,
        f"results-0-score": participants[0].score,
        f"results-0-result": Result.WIN,
        f"results-0-placement": participants[0].placement,
        f"results-1-id": participants[1].pk,
        f"results-1-player": participants[1].player_id,
        f"results-1-score": participants[1].score,
        f"results-1-result": Result.LOSS,
        f"results-1-placement": participants[1].placement,
    }
    formset = _inline_formset(game=backgammon_game, data=data)
    assert formset.is_valid(), formset.errors
    saved_results = [
        form.cleaned_data["result"]
        for form in formset.forms
        if form.cleaned_data and not form.cleaned_data.get("DELETE")
    ]
    assert saved_results == [Result.WIN, Result.PLAYED]


@pytest.mark.django_db
def test_game_admin_save_backgammon_with_played_result(
    client, admin_user, backgammon_game
):
    client.force_login(admin_user)
    participants = list(backgammon_game.participant_results.order_by("pk"))
    url = reverse("admin:games_game_change", args=[backgammon_game.pk])
    response = client.get(url)
    assert response.status_code == 200

    data = {
        "group": backgammon_game.group_id,
        "game_type_code": "backgammon",
        "played_on": backgammon_game.played_on.isoformat(),
        "recorded_by": backgammon_game.recorded_by_id,
        "notes": "",
        "player_count": 2,
        "double_weight": 1,
        "half_weight": 1,
        "score_type": "",
        "location": "",
        "import_source": "",
        "import_row_key": "",
        "participant_results-TOTAL_FORMS": "2",
        "participant_results-INITIAL_FORMS": "2",
        "participant_results-MIN_NUM_FORMS": "0",
        "participant_results-MAX_NUM_FORMS": "1000",
        f"participant_results-0-id": participants[0].pk,
        f"participant_results-0-player": participants[0].player_id,
        f"participant_results-0-score": participants[0].score,
        f"participant_results-0-result": Result.WIN,
        f"participant_results-0-placement": participants[0].placement,
        f"participant_results-1-id": participants[1].pk,
        f"participant_results-1-player": participants[1].player_id,
        f"participant_results-1-score": participants[1].score,
        f"participant_results-1-result": Result.PLAYED,
        f"participant_results-1-placement": participants[1].placement,
    }
    response = client.post(url, data)
    assert response.status_code == 302, response.content.decode()
    backgammon_game.refresh_from_db()
    results = list(backgammon_game.participant_results.order_by("pk"))
    assert results[0].result == Result.WIN
    assert results[1].result == Result.PLAYED


@pytest.mark.django_db
def test_game_participant_result_clean_normalizes_loss_for_backgammon(backgammon_game):
    participant = backgammon_game.participant_results.order_by("pk").last()
    participant.result = Result.LOSS
    participant.clean()
    assert participant.result == Result.PLAYED


@pytest.mark.django_db
def test_game_participant_result_clean_keeps_loss_for_progressive_rummy(
    admin_user, group
):
    players = list(group.players.order_by("pk"))
    game = Game.objects.create(
        group=group,
        game_type_code="progressiverummy",
        played_on=timezone.localdate(),
        recorded_by=admin_user,
        player_count=2,
    )
    participant = GameParticipantResult(
        game=game,
        player=players[1],
        score=50,
        result=Result.LOSS,
        placement=1,
    )
    participant.clean()
    assert participant.result == Result.LOSS
