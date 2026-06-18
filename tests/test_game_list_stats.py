import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone

from leaderlodge.games.list_stats import build_game_list_stats
from leaderlodge.games.models import GameParticipantResult
from leaderlodge.games.views import _filtered_games_queryset
from leaderlodge.groups.services import add_guest_player, create_group_with_owner


@pytest.fixture
def user(db):
    return User.objects.create_user(username="david", password="test-pass-123")


@pytest.fixture
def group(user):
    group = create_group_with_owner(user=user, name="Dom Club")
    add_guest_player(group=group, display_name="Pat")
    return group


def _players_pair(group):
    return list(group.players.order_by("pk"))[:2]


def _record_game(group, *, game_type_code="dominos", scores=None, location_name=""):
    from leaderlodge.games.scoring import assign_results_from_scores
    from leaderlodge.games.services import ParticipantInput, record_game

    players = _players_pair(group)
    if scores is None:
        scores = {players[0].pk: 30, players[1].pk: 20}

    participant_rows = [
        {"player": player, "score": scores[player.pk]}
        for player in players
    ]
    assign_results_from_scores(participant_rows, game_type_code)

    participants = [
        ParticipantInput(
            player=row["player"],
            score=row["score"],
            result=row["result"],
            placement=row["placement"],
        )
        for row in participant_rows
    ]

    location = None
    if location_name:
        from leaderlodge.groups.locations import resolve_game_location

        location = resolve_game_location(group=group, location_name=location_name)

    return record_game(
        user=group.created_by,
        group=group,
        game_type_code=game_type_code,
        played_on=timezone.localdate(),
        participants=participants,
        location=location,
    )


@pytest.mark.django_db
def test_build_game_list_stats_aggregates_all_filtered_games(user, group):
    players = _players_pair(group)
    _record_game(group, scores={players[0].pk: 30, players[1].pk: 20})
    _record_game(group, scores={players[0].pk: 25, players[1].pk: 25})
    _record_game(group, scores={players[0].pk: 10, players[1].pk: 40})

    params = {"group": str(group.pk), "game_type": "dominos", "location": "", "sort": "desc"}
    games_qs = _filtered_games_queryset(user, params)
    stats = build_game_list_stats(games_qs=games_qs, game_type_code="dominos")

    assert stats is not None
    assert stats.total_games == 3
    assert stats.show_losses is False
    assert stats.global_max_score == 40
    assert stats.global_min_score == 10
    assert len(stats.players) == 2

    by_label = {item.player.display_label: item for item in stats.players}
    owner = group.players.get(linked_user=user)
    pat = group.players.get(display_name="Pat")

    assert by_label[owner.display_label].wins == 1
    assert by_label[owner.display_label].ties == 1
    assert by_label[owner.display_label].total_points == 65
    assert by_label[owner.display_label].max_score == 30
    assert by_label[owner.display_label].min_score == 10

    assert by_label[pat.display_label].wins == 1
    assert by_label[pat.display_label].ties == 1
    assert by_label[pat.display_label].total_points == 85
    assert by_label[pat.display_label].max_score == 40
    assert by_label[pat.display_label].min_score == 20


@pytest.mark.django_db
def test_build_game_list_stats_respects_location_filter(user, group):
    players = _players_pair(group)
    _record_game(group, scores={players[0].pk: 30, players[1].pk: 20}, location_name="Sally")
    _record_game(group, scores={players[0].pk: 10, players[1].pk: 40}, location_name="Kitchen")

    from leaderlodge.groups.locations import get_or_create_location

    sally = get_or_create_location(library=group.location_library, name="Sally")
    params = {
        "group": str(group.pk),
        "game_type": "dominos",
        "location": str(sally.pk),
        "sort": "desc",
    }
    games_qs = _filtered_games_queryset(user, params)
    stats = build_game_list_stats(games_qs=games_qs, game_type_code="dominos")

    assert stats.total_games == 1
    assert stats.global_max_score == 30
    assert stats.global_min_score == 20


@pytest.mark.django_db
def test_build_game_list_stats_shows_losses_for_progressive_rummy(user, group):
    players = list(group.players.order_by("pk"))
    while len(players) < 3:
        players.append(add_guest_player(group=group, display_name=f"Guest{len(players)}"))

    from leaderlodge.games.services import ParticipantInput, record_game

    record_game(
        user=group.created_by,
        group=group,
        game_type_code="progressiverummy",
        played_on=timezone.localdate(),
        participants=[
            ParticipantInput(
                player=players[0],
                score=10,
                result=GameParticipantResult.Result.WIN,
                placement=1,
            ),
            ParticipantInput(
                player=players[1],
                score=20,
                result=GameParticipantResult.Result.LOSS,
                placement=2,
            ),
            ParticipantInput(
                player=players[2],
                score=20,
                result=GameParticipantResult.Result.LOSS,
                placement=3,
            ),
        ],
    )

    params = {
        "group": str(group.pk),
        "game_type": "progressiverummy",
        "location": "",
        "sort": "desc",
    }
    games_qs = _filtered_games_queryset(user, params)
    stats = build_game_list_stats(games_qs=games_qs, game_type_code="progressiverummy")

    assert stats.show_losses is True
    losses = {item.player.pk: item.losses for item in stats.players}
    assert losses[players[1].pk] == 1
    assert losses[players[2].pk] == 1


@pytest.mark.django_db
def test_game_list_stats_use_full_filter_not_current_page(client, user, group, monkeypatch):
    from leaderlodge.games import views as game_views

    monkeypatch.setattr(game_views, "GAMES_PER_PAGE", 1)

    client.force_login(user)
    players = _players_pair(group)
    _record_game(group, scores={players[0].pk: 30, players[1].pk: 20})
    _record_game(group, scores={players[0].pk: 25, players[1].pk: 25})
    _record_game(group, scores={players[0].pk: 10, players[1].pk: 40})

    response = client.get(
        reverse("games:list"),
        {"group": str(group.pk), "game_type": "dominos", "page": 1},
    )
    content = response.content.decode()

    assert response.status_code == 200
    assert "Stats" in content
    assert "(3 games)" in content
    assert "High score" in content
    assert "Page 1 of 3" in content


@pytest.mark.django_db
def test_game_list_hides_location_column_when_filtered(client, user, group):
    players = _players_pair(group)
    game = _record_game(
        group,
        scores={players[0].pk: 30, players[1].pk: 20},
        location_name="Sally",
    )

    client.force_login(user)
    response = client.get(
        reverse("games:list"),
        {
            "group": str(group.pk),
            "game_type": "dominos",
            "location": str(game.location_id),
        },
    )
    content = response.content.decode()

    assert response.status_code == 200
    assert content.count('<th scope="col">Location</th>') == 0
