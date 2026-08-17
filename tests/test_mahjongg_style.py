import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone

from leaderlodge.games.models import GameParticipantResult, GameScoreChangeLog
from leaderlodge.games.registry import MahjonggStyle, normalize_score_type
from leaderlodge.games.services import ParticipantInput, record_game
from leaderlodge.groups.services import add_guest_player, create_group_with_owner
from tests.conftest import edit_game_participant_post


@pytest.fixture
def user(db):
    return User.objects.create_user(username="david", password="test-pass-123")


@pytest.fixture
def group(user):
    group = create_group_with_owner(user=user, name="MJ Club")
    add_guest_player(group=group, display_name="Pat")
    add_guest_player(group=group, display_name="Sam")
    return group


def _three_players(group):
    return list(group.players.filter(is_team=False).order_by("pk")[:3])


@pytest.mark.django_db
def test_normalize_mahjongg_style_defaults_american():
    assert normalize_score_type("mahjongg", "") == MahjonggStyle.AMERICAN.value
    assert (
        normalize_score_type("mahjongg", MahjonggStyle.JAPANESE.value)
        == MahjonggStyle.JAPANESE.value
    )


@pytest.mark.django_db
def test_record_mahjongg_persists_style_and_defaults_next(client, user, group):
    from tests.test_games import _load_roster_post

    players = _three_players(group)
    client.force_login(user)

    record_game(
        user=user,
        group=group,
        game_type_code="mahjongg",
        played_on=timezone.localdate(),
        score_type=MahjonggStyle.HONG_KONG.value,
        participants=[
            ParticipantInput(
                player=players[0],
                score=100,
                result=GameParticipantResult.Result.WIN,
                placement=0,
            ),
            ParticipantInput(
                player=players[1],
                score=50,
                result=GameParticipantResult.Result.PLAYED,
                placement=1,
            ),
            ParticipantInput(
                player=players[2],
                score=25,
                result=GameParticipantResult.Result.PLAYED,
                placement=2,
            ),
        ],
    )

    game = group.games.get()
    assert game.score_type == MahjonggStyle.HONG_KONG.value

    response = client.post(
        reverse("games:create"),
        _load_roster_post(group, game_type_code="mahjongg"),
    )
    assert response.status_code == 200
    content = response.content.decode()
    assert ">Style<" in content or "Style</label>" in content
    assert f'value="{MahjonggStyle.HONG_KONG.value}"' in content
    assert f'value="{MahjonggStyle.HONG_KONG.value}"' in content
    assert "selected" in content
    assert "mj-hong-kong.png" in content


@pytest.mark.django_db
def test_legacy_empty_mahjongg_style_counts_as_american(client, user, group):
    players = _three_players(group)
    client.force_login(user)
    game = record_game(
        user=user,
        group=group,
        game_type_code="mahjongg",
        played_on=timezone.localdate(),
        score_type=MahjonggStyle.AMERICAN.value,
        participants=[
            ParticipantInput(
                player=players[0],
                score=100,
                result=GameParticipantResult.Result.WIN,
                placement=0,
            ),
            ParticipantInput(
                player=players[1],
                score=50,
                result=GameParticipantResult.Result.PLAYED,
                placement=1,
            ),
            ParticipantInput(
                player=players[2],
                score=25,
                result=GameParticipantResult.Result.PLAYED,
                placement=2,
            ),
        ],
    )
    # Simulate legacy rows that never stored a style.
    type(game).objects.filter(pk=game.pk).update(score_type="")

    list_response = client.get(
        reverse("games:list"),
        {"group": str(group.pk), "type": "mahjongg", "score_type": "american"},
    )
    assert list_response.status_code == 200
    assert list_response.context["page"].paginator.count == 1

    detail = client.get(reverse("games:detail", kwargs={"pk": game.pk}))
    assert detail.status_code == 200
    content = detail.content.decode()
    assert "Style: American" in content
    assert "mj-american.png" in content


@pytest.mark.django_db
def test_game_list_shows_mahjongg_style_icon(client, user, group):
    players = _three_players(group)
    client.force_login(user)
    record_game(
        user=user,
        group=group,
        game_type_code="mahjongg",
        played_on=timezone.localdate(),
        score_type=MahjonggStyle.TAIWANESE.value,
        participants=[
            ParticipantInput(
                player=players[0],
                score=100,
                result=GameParticipantResult.Result.WIN,
                placement=0,
            ),
            ParticipantInput(
                player=players[1],
                score=50,
                result=GameParticipantResult.Result.PLAYED,
                placement=1,
            ),
            ParticipantInput(
                player=players[2],
                score=25,
                result=GameParticipantResult.Result.PLAYED,
                placement=2,
            ),
        ],
    )

    response = client.get(
        reverse("games:list"),
        {"group": str(group.pk), "type": "mahjongg"},
        follow=True,
    )
    assert response.status_code == 200
    content = response.content.decode()
    assert "game-list-weight-col" in content
    assert "mj-taiwan.png" in content
    assert "game-list-style-icon" in content
    assert 'title="Taiwanese"' in content


@pytest.mark.django_db
def test_edit_mahjongg_style(client, user, group):
    players = _three_players(group)
    client.force_login(user)
    game = record_game(
        user=user,
        group=group,
        game_type_code="mahjongg",
        played_on=timezone.localdate(),
        score_type=MahjonggStyle.AMERICAN.value,
        participants=[
            ParticipantInput(
                player=players[0],
                score=100,
                result=GameParticipantResult.Result.WIN,
                placement=0,
            ),
            ParticipantInput(
                player=players[1],
                score=50,
                result=GameParticipantResult.Result.PLAYED,
                placement=1,
            ),
            ParticipantInput(
                player=players[2],
                score=25,
                result=GameParticipantResult.Result.PLAYED,
                placement=2,
            ),
        ],
    )
    participants = list(game.participant_results.order_by("pk"))
    url = reverse("games:edit_game", kwargs={"pk": game.pk})

    response = client.get(url)
    assert response.status_code == 200
    content = response.content.decode()
    assert "Style" in content
    assert MahjonggStyle.JAPANESE.value in content
    assert "mj-american.png" in content

    response = client.post(
        url,
        edit_game_participant_post(
            game,
            score_type=MahjonggStyle.JAPANESE.value,
            notes="Recorded American by mistake.",
        ),
    )
    assert response.status_code == 302
    game.refresh_from_db()
    assert game.score_type == MahjonggStyle.JAPANESE.value
    log = GameScoreChangeLog.objects.get(game=game)
    assert log.old_snapshot["score_type"] == MahjonggStyle.AMERICAN.value
    assert log.new_snapshot["score_type"] == MahjonggStyle.JAPANESE.value
