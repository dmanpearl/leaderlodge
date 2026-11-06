import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone

from leaderlodge.games.models import Game, GameParticipantResult
from leaderlodge.games.services import ParticipantInput, record_game
from leaderlodge.groups.locations import normalize_location_name
from leaderlodge.groups.models import Location
from leaderlodge.groups.services import add_guest_player, create_group_with_owner

from tests.test_games import _save_game_post


@pytest.fixture
def user(db):
    return User.objects.create_user(username="david", password="test-pass-123")


@pytest.fixture
def group(user):
    group = create_group_with_owner(user=user, name="Dom Club")
    add_guest_player(group=group, display_name="Pat")
    return group


def _players(group, count):
    players = list(group.players.order_by("pk"))
    while len(players) < count:
        players.append(
            add_guest_player(group=group, display_name=f"Guest{len(players)}")
        )
    return players[:count]


@pytest.mark.django_db
def test_save_for_later_stores_score_and_turn_outside_standings(client, user, group):
    players = _players(group, 2)
    data = _save_game_post(
        group,
        players_played=players[:1],
        scores={players[0].pk: 12},
    )
    data["action"] = "save_later"
    data["turn_side"] = "0"

    client.force_login(user)
    response = client.post(reverse("games:create"), data)
    game = Game.objects.get()
    assert response.status_code == 302
    assert response.url == reverse("games:resume", kwargs={"pk": game.pk})
    assert game.paused is True
    assert game.turn_player_id == players[0].pk
    assert game.participant_results.get().score == 12
    assert game.participant_results.get().result == GameParticipantResult.Result.PLAYED
    assert Game.finished.count() == 0
    assert GameParticipantResult.finished.count() == 0


@pytest.mark.django_db
def test_resume_updates_score_then_finish_counts_the_win(client, user, group):
    players = _players(group, 2)
    client.force_login(user)
    start = _save_game_post(
        group,
        players_played=players,
        scores={players[0].pk: 10, players[1].pk: 4},
    )
    start["action"] = "save_later"
    start["turn_side"] = "1"
    client.post(reverse("games:create"), start)
    game = Game.objects.get()

    page = client.get(reverse("games:resume", kwargs={"pk": game.pk}))
    content = page.content.decode()
    assert page.status_code == 200
    assert "In progress" in content
    assert "Save for later" in content
    assert "data-game-record-voice" not in content
    assert 'id="player-picker-input"' not in content
    assert "data-remove-side" not in content
    assert "Whose turn is it?" in content
    assert "game-record-turn-mark" in content
    assert 'type="radio"' not in content

    updated = _save_game_post(
        group,
        players_played=players,
        scores={players[0].pk: 42, players[1].pk: 38},
    )
    updated["action"] = "save_later"
    updated["turn_side"] = "0"
    client.post(reverse("games:resume", kwargs={"pk": game.pk}), updated)
    game.refresh_from_db()
    assert game.paused is True
    assert game.turn_player_id == players[0].pk
    assert set(game.participant_results.values_list("score", flat=True)) == {42, 38}
    assert Game.finished.count() == 0

    finished = _save_game_post(
        group,
        players_played=players,
        scores={players[0].pk: 55, players[1].pk: 40},
    )
    response = client.post(reverse("games:resume", kwargs={"pk": game.pk}), finished)
    game.refresh_from_db()
    assert response.status_code == 302
    assert game.paused is False
    assert game.turn_player_id is None
    assert Game.finished.filter(pk=game.pk).exists()
    assert GameParticipantResult.finished.filter(
        game=game,
        player=players[0],
        result=GameParticipantResult.Result.WIN,
    ).exists()


@pytest.mark.django_db
def test_discard_removes_paused_game(client, user, group):
    players = _players(group, 1)
    client.force_login(user)
    data = _save_game_post(group, players_played=players, scores={players[0].pk: 1})
    data["action"] = "save_later"
    client.post(reverse("games:create"), data)
    game = Game.objects.get()

    response = client.post(
        reverse("games:resume", kwargs={"pk": game.pk}),
        {"action": "discard"},
    )
    assert response.status_code == 302
    assert Game.objects.count() == 0


@pytest.mark.django_db
def test_games_list_toggles_paused_games(client, user, group):
    players = _players(group, 2)
    client.force_login(user)
    paused = _save_game_post(
        group,
        players_played=players,
        scores={players[0].pk: 3, players[1].pk: 1},
    )
    paused["action"] = "save_later"
    client.post(reverse("games:create"), paused)
    finished = _save_game_post(
        group,
        players_played=players,
        scores={players[0].pk: 30, players[1].pk: 10},
    )
    client.post(reverse("games:create"), finished)

    finished_page = client.get(reverse("games:list") + "?type=dominos", follow=True)
    finished_html = finished_page.content.decode()
    assert "In progress (1)" in finished_html
    assert (
        reverse("games:resume", kwargs={"pk": Game.objects.get(paused=True).pk})
        not in finished_html
    )

    paused_page = client.get(
        reverse("games:list") + "?type=dominos&status=paused", follow=True
    )
    paused_html = paused_page.content.decode()
    assert ">Finished<" in paused_html
    assert "Stats" not in paused_html
    assert (
        reverse("games:resume", kwargs={"pk": Game.objects.get(paused=True).pk})
        in paused_html
    )


@pytest.mark.django_db
def test_add_page_lists_paused_games_for_the_selected_type(client, user, group):
    players = _players(group, 2)
    client.force_login(user)
    data = _save_game_post(
        group,
        players_played=players,
        scores={players[0].pk: 8, players[1].pk: 2},
    )
    data["action"] = "save_later"
    client.post(reverse("games:create"), data)
    game = Game.objects.get()
    game.location = Location.objects.create(
        library=group.location_library,
        name="The Lodge",
        normalized_name=normalize_location_name("The Lodge"),
    )
    game.save(update_fields=["location"])

    page = client.get(reverse("games:create") + f"?group={group.pk}&type=dominos")
    html = page.content.decode()
    assert "In progress (1)" in html
    assert 'id="paused-games-list"' in html
    assert "collapse" in html
    listed = html.split('id="paused-games-list"', 1)[1].split("</div>", 1)[0]
    assert " ," not in listed
    assert "The Lodge, david 8, Pat 2" in listed

    other = client.get(reverse("games:create") + f"?group={group.pk}&type=backgammon")
    assert "In progress (" not in other.content.decode()


@pytest.mark.django_db
def test_dashboard_opens_the_latest_paused_game(client, user, group):
    players = _players(group, 2)
    played_on = timezone.localdate()
    record_game(
        user=user,
        group=group,
        game_type_code="dominos",
        played_on=played_on,
        participants=[
            ParticipantInput(
                player=players[0],
                score=1,
                result=GameParticipantResult.Result.PLAYED,
                placement=0,
            ),
            ParticipantInput(
                player=players[1],
                score=2,
                result=GameParticipantResult.Result.PLAYED,
                placement=0,
            ),
        ],
        paused=True,
        turn_player=players[1],
    )
    game = Game.objects.get()
    client.force_login(user)
    response = client.get(reverse("core:dashboard"))
    assert response.status_code == 302
    assert response.url == reverse("games:resume", kwargs={"pk": game.pk})


@pytest.mark.django_db
def test_resume_keeps_wall_game_editable(client, user, group):
    players = _players(group, 3)
    record_game(
        user=user,
        group=group,
        game_type_code="mahjongg",
        played_on=timezone.localdate(),
        participants=[
            ParticipantInput(
                player=player,
                score=10,
                result=GameParticipantResult.Result.PLAYED,
                placement=0,
            )
            for player in players
        ],
        paused=True,
    )
    game = Game.objects.get()
    client.force_login(user)
    html = client.get(reverse("games:resume", kwargs={"pk": game.pk})).content.decode()
    assert 'name="is_no_score_tie"' in html
    assert "data-no-score-toggle" in html
    assert "checked" in html
