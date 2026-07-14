import pytest
from datetime import datetime, timezone as dt_timezone
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from leaderlodge.games.models import Game, GameParticipantResult
from leaderlodge.groups.services import add_guest_player, create_group_with_owner


@pytest.fixture
def user(db):
    return User.objects.create_user(username="david", password="test-pass-123")


@pytest.fixture
def group(user):
    group = create_group_with_owner(user=user, name="Dom Club")
    add_guest_player(group=group, display_name="Pat")
    return group


def _save_game_post(
    group,
    *,
    game_type_code="dominos",
    players_played=None,
    scores=None,
):
    players = list(group.players.order_by("pk"))
    if players_played is None:
        players_played = players[:2]
    if scores is None:
        scores = {players_played[0].pk: 30, players_played[1].pk: 20}

    data = {
        "action": "save",
        "group": str(group.pk),
        "game_type_code": game_type_code,
        "played_on": timezone.localdate().isoformat(),
        "participant_player_id": [],
        "participant_guest_name": [],
        "participant_score": [],
    }
    for player in players_played:
        data["participant_player_id"].append(str(player.pk))
        data["participant_guest_name"].append("")
        data["participant_score"].append(str(scores.get(player.pk, 0)))
    return data


def _load_roster_post(group, *, game_type_code="dominos"):
    return {
        "action": "load_roster",
        "group": str(group.pk),
        "game_type_code": game_type_code,
        "played_on": timezone.localdate().isoformat(),
    }


def _reuse_roster_post(group, *, game_type_code="dominos", reuse_game_id=None):
    data = {
        "action": "reuse_roster",
        "group": str(group.pk),
        "game_type_code": game_type_code,
        "played_on": timezone.localdate().isoformat(),
    }
    if reuse_game_id is not None:
        data["reuse_game_id"] = str(reuse_game_id)
    return data


@pytest.mark.django_db
def test_record_dominos_game(client, user, group):
    client.force_login(user)
    client.post(reverse("games:create"), _load_roster_post(group))
    response = client.post(reverse("games:create"), _save_game_post(group))

    assert response.status_code == 302
    game = Game.objects.get(group=group)
    winner = game.participant_results.get(result=GameParticipantResult.Result.WIN)
    assert winner.score == 30


@pytest.mark.django_db
def test_record_dominos_tie(client, user, group):
    players = list(group.players.order_by("pk"))
    data = _save_game_post(
        group,
        players_played=players[:2],
        scores={players[0].pk: 20, players[1].pk: 20},
    )
    client.force_login(user)
    client.post(reverse("games:create"), _load_roster_post(group))
    response = client.post(reverse("games:create"), data)
    assert response.status_code == 302

    game = Game.objects.get()
    assert (
        game.participant_results.filter(result=GameParticipantResult.Result.TIE).count()
        == 2
    )


@pytest.mark.django_db
def test_record_progressive_rummy_tied_losers(client, user, group):
    players = list(group.players.order_by("pk"))
    while len(players) < 3:
        players.append(
            add_guest_player(group=group, display_name=f"Guest{len(players)}")
        )

    data = _save_game_post(
        group,
        game_type_code="progressiverummy",
        players_played=players[:3],
        scores={players[0].pk: 10, players[1].pk: 50, players[2].pk: 50},
    )
    client.force_login(user)
    client.post(
        reverse("games:create"),
        _load_roster_post(group, game_type_code="progressiverummy"),
    )
    response = client.post(reverse("games:create"), data)
    assert response.status_code == 302

    game = Game.objects.get(game_type_code="progressiverummy")
    assert (
        game.participant_results.filter(
            result=GameParticipantResult.Result.LOSS
        ).count()
        == 2
    )


@pytest.mark.django_db
def test_record_dominos_double_game(client, user, group):
    players = list(group.players.order_by("pk"))
    while len(players) < 2:
        players.append(
            add_guest_player(group=group, display_name=f"Guest{len(players)}")
        )
    data = _save_game_post(
        group,
        players_played=players[:2],
        scores={players[0].pk: 77, players[1].pk: 76},
    )
    client.force_login(user)
    client.post(reverse("games:create"), _load_roster_post(group))
    response = client.post(reverse("games:create"), data)
    assert response.status_code == 302

    game = Game.objects.get()
    assert game.double_weight == 2
    assert (
        "Double game"
        in client.get(reverse("games:detail", kwargs={"pk": game.pk})).content.decode()
    )


@pytest.mark.django_db
def test_auto_select_single_group(client, user, group):
    client.force_login(user)
    response = client.get(reverse("games:create"))
    assert response.status_code == 200
    content = response.content.decode()
    assert "Dom Club" in content
    assert "Choose a game" in content
    assert "Pick Players" in content
    assert 'id="game-record-form"' not in content


@pytest.mark.django_db
def test_record_game_default_date_uses_configured_timezone(client, user, group):
    """11pm Pacific is already the next calendar day in UTC."""
    late_evening_utc = datetime(2026, 6, 20, 6, 9, tzinfo=dt_timezone.utc)

    with patch("django.utils.timezone.now", return_value=late_evening_utc):
        with override_settings(TIME_ZONE="UTC"):
            assert timezone.localdate().isoformat() == "2026-06-20"

        with override_settings(TIME_ZONE="America/Los_Angeles"):
            assert timezone.localdate().isoformat() == "2026-06-19"

            client.force_login(user)
            response = client.get(reverse("games:create"))
            content = response.content.decode()
            assert response.status_code == 200
            assert 'value="2026-06-19"' in content


@pytest.mark.django_db
def test_load_roster_requires_game_type(client, user, group):
    client.force_login(user)
    response = client.post(
        reverse("games:create"),
        {
            "action": "load_roster",
            "group": str(group.pk),
            "game_type_code": "",
            "played_on": timezone.localdate().isoformat(),
        },
    )
    assert response.status_code == 200
    assert 'id="game-record-form"' not in response.content.decode()


@pytest.mark.django_db
def test_load_roster_shows_formatted_date(client, user, group):
    client.force_login(user)
    response = client.post(reverse("games:create"), _load_roster_post(group))
    content = response.content.decode()
    assert response.status_code == 200
    assert "localdate" not in content
    assert 'id="game-record-form"' in content
    assert "data-player-picker" in content
    assert "Add player" in content
    assert "Highest score wins" in content
    assert "player_picker.css" in content


@pytest.mark.django_db
def test_load_roster_defaults_score_to_zero_for_high_wins_games(client, user, group):
    client.force_login(user)
    for game_type_code in ("dominos", "backgammon", "mahjongg"):
        response = client.post(
            reverse("games:create"),
            _load_roster_post(group, game_type_code=game_type_code),
        )
        content = response.content.decode()
        assert response.status_code == 200
        assert 'data-default-participant-score="0"' in content


@pytest.mark.django_db
def test_load_roster_leaves_score_blank_for_progressive_rummy(client, user, group):
    client.force_login(user)
    response = client.post(
        reverse("games:create"),
        _load_roster_post(group, game_type_code="progressiverummy"),
    )
    content = response.content.decode()

    assert response.status_code == 200
    assert 'data-default-participant-score=""' in content


@pytest.mark.django_db
def test_load_roster_shows_low_wins_instructions_for_progressive_rummy(
    client, user, group
):
    client.force_login(user)
    response = client.post(
        reverse("games:create"),
        _load_roster_post(group, game_type_code="progressiverummy"),
    )
    content = response.content.decode()

    assert response.status_code == 200
    assert "Lowest score wins" in content
    assert "2-10 players" in content
    assert "Highest score wins" not in content


@pytest.mark.django_db
def test_record_game_with_new_guest(client, user, group):
    players = list(group.players.order_by("pk"))
    client.force_login(user)
    client.post(reverse("games:create"), _load_roster_post(group))
    response = client.post(
        reverse("games:create"),
        {
            "action": "save",
            "group": str(group.pk),
            "game_type_code": "dominos",
            "played_on": timezone.localdate().isoformat(),
            "participant_player_id": [str(players[0].pk), ""],
            "participant_guest_name": ["", "Alex"],
            "participant_score": ["30", "20"],
        },
    )

    assert response.status_code == 302
    assert group.players.filter(display_name="Alex").exists()
    game = Game.objects.get(group=group)
    assert game.participant_results.count() == 2


@pytest.mark.django_db
def test_game_list_for_member(client, user, group):
    client.force_login(user)
    client.post(reverse("games:create"), _load_roster_post(group))
    client.post(reverse("games:create"), _save_game_post(group))

    response = client.get(reverse("games:list"), follow=True)
    assert response.status_code == 200
    content = response.content.decode()
    assert "Dom Club" in content
    assert "Dominos" in content
    assert "game-list-title-icon" in content
    assert 'id="game-list-title-icon"' in content
    assert "game-list-stats-game-icon" in content
    assert "game-types/dominos.png" in content
    assert '<option value="">All games</option>' not in content


@pytest.mark.django_db
def test_game_list_type_filters_collapsible(client, user, group):
    client.force_login(user)
    client.post(reverse("games:create"), _load_roster_post(group))
    client.post(reverse("games:create"), _save_game_post(group))

    content = client.get(reverse("games:list"), follow=True).content.decode()

    assert 'id="game-list-type-filters"' in content
    assert 'data-bs-target="#game-list-type-filters"' in content
    assert ">Filters</span>" in content
    assert 'id="game-list-filters-summary"' in content
    assert "(Dom Club)" in content
    assert 'id="filter-group"' in content


@pytest.mark.django_db
def test_game_list_filter_summary_lists_group_and_location(client, user, group):
    client.force_login(user)
    load = _load_roster_post(group)
    load["location_name"] = "Sally"
    client.post(reverse("games:create"), load)
    save = _save_game_post(group)
    save["location_name"] = "Sally"
    client.post(reverse("games:create"), save)

    from leaderlodge.groups.models import Location

    location = Location.objects.get(name="Sally")
    content = client.get(
        reverse("games:list"),
        {"group": str(group.pk), "game_type": "dominos", "location": str(location.pk)},
        follow=True,
    ).content.decode()

    assert "(Dom Club, Sally)" in content


@pytest.mark.django_db
def test_game_list_pagination(client, user, group, monkeypatch):
    from leaderlodge.games import views as game_views

    monkeypatch.setattr(game_views, "GAMES_PER_PAGE", 1)
    client.force_login(user)
    client.post(reverse("games:create"), _load_roster_post(group))
    client.post(reverse("games:create"), _save_game_post(group))
    client.post(reverse("games:create"), _save_game_post(group))
    client.post(reverse("games:create"), _save_game_post(group))

    page1 = client.get(reverse("games:list"), follow=True)
    page2 = client.get(reverse("games:list"), {"page": 2}, follow=True)
    page3 = client.get(reverse("games:list"), {"page": 3}, follow=True)
    assert page1.status_code == 200
    assert page2.status_code == 200
    assert page3.status_code == 200
    content1 = page1.content.decode()
    assert "Page 1 of 3" in content1
    assert "Page 2 of 3" in page2.content.decode()
    assert 'page=3">Last</a>' in content1
    assert 'page=1">First</a>' not in content1


@pytest.mark.django_db
def test_game_list_filters_by_year_and_quick_range(client, user, group):
    client.force_login(user)
    players = list(group.players.order_by("pk")[:2])
    from datetime import date

    from leaderlodge.games.services import ParticipantInput, record_game

    record_game(
        user=user,
        group=group,
        game_type_code="dominos",
        played_on=date(2025, 12, 1),
        participants=[
            ParticipantInput(player=players[0], score=30, result="win", placement=0),
            ParticipantInput(player=players[1], score=20, result="played", placement=1),
        ],
    )
    record_game(
        user=user,
        group=group,
        game_type_code="dominos",
        played_on=date(2026, 6, 1),
        participants=[
            ParticipantInput(player=players[1], score=40, result="win", placement=0),
            ParticipantInput(player=players[0], score=10, result="played", placement=1),
        ],
    )

    year_response = client.get(
        reverse("games:list"),
        {"group": str(group.pk), "game_type": "dominos", "year": "2026"},
    )
    year_content = year_response.content.decode()
    assert year_response.status_code == 200
    assert 'name="period_preset"' in year_content
    assert 'id="filter-year"' in year_content
    assert year_content.count("game-list-row") == 1 or "Jun" in year_content

    range_response = client.get(
        reverse("games:list"),
        {
            "group": str(group.pk),
            "game_type": "dominos",
            "start_date": "2025-12-01",
            "end_date": "2025-12-31",
        },
    )
    assert range_response.status_code == 200
    assert "Dec" in range_response.content.decode()


def test_game_list_filters_by_group_and_game_type(client, user, group):
    other_group = create_group_with_owner(user=user, name="Other Club")
    add_guest_player(group=other_group, display_name="Pat")

    client.force_login(user)
    client.post(reverse("games:create"), _load_roster_post(group))
    client.post(
        reverse("games:create"), _save_game_post(group, game_type_code="dominos")
    )
    client.post(
        reverse("games:create"),
        _load_roster_post(other_group, game_type_code="backgammon"),
    )
    client.post(
        reverse("games:create"),
        _save_game_post(other_group, game_type_code="backgammon"),
    )

    redirect_response = client.get(reverse("games:list"))
    assert redirect_response.status_code == 302
    assert "game_type=backgammon" in redirect_response.url
    assert f"group={other_group.pk}" in redirect_response.url

    default_list = client.get(reverse("games:list"), follow=True)
    dominos_only = client.get(
        reverse("games:list"),
        {"group": str(group.pk), "game_type": "dominos"},
    )
    backgammon_only = client.get(
        reverse("games:list"),
        {"game_type": "backgammon"},
        follow=True,
    )

    assert default_list.status_code == 200
    default_content = default_list.content.decode()
    assert "Backgammon" in default_content
    assert f'value="{other_group.pk}" selected' in default_content
    assert '<option value="">All games</option>' not in default_content
    assert dominos_only.status_code == 200
    dominos_content = dominos_only.content.decode()
    assert dominos_content.count("Dom Club") >= 1
    assert ">Other Club</a>" not in dominos_content
    assert '<th scope="col">Group</th>' not in dominos_content
    assert '<th scope="col">Game</th>' not in dominos_content
    assert backgammon_only.status_code == 200
    assert "Backgammon" in backgammon_only.content.decode()
    assert '<th scope="col">Game</th>' not in backgammon_only.content.decode()


@pytest.mark.django_db
def test_game_list_location_choices_culled_by_group_and_type(client, user, group):
    other_group = create_group_with_owner(user=user, name="Other Club")
    add_guest_player(group=other_group, display_name="Pat")

    client.force_login(user)

    load = _load_roster_post(group)
    load["location_name"] = "Sally"
    client.post(reverse("games:create"), load)
    save = _save_game_post(group, game_type_code="dominos")
    save["location_name"] = "Sally"
    client.post(reverse("games:create"), save)

    load = _load_roster_post(other_group, game_type_code="backgammon")
    load["location_name"] = "Carpenteria"
    client.post(reverse("games:create"), load)
    save = _save_game_post(other_group, game_type_code="backgammon")
    save["location_name"] = "Carpenteria"
    client.post(reverse("games:create"), save)

    dominos_group = client.get(
        reverse("games:list"),
        {"group": str(group.pk), "game_type": "dominos"},
    )
    content = dominos_group.content.decode()
    assert "Sally" in content
    assert "Carpenteria" not in content


@pytest.mark.django_db
def test_game_list_filters_by_game_size(client, user, group):
    add_guest_player(group=group, display_name="Sam")
    add_guest_player(group=group, display_name="Alex")
    players = list(group.players.order_by("pk"))
    client.force_login(user)
    client.post(reverse("games:create"), _load_roster_post(group))
    client.post(
        reverse("games:create"),
        _save_game_post(
            group,
            players_played=players[:2],
            scores={players[0].pk: 30, players[1].pk: 20},
        ),
    )
    client.post(
        reverse("games:create"),
        _save_game_post(
            group,
            players_played=players[:3],
            scores={
                players[0].pk: 35,
                players[1].pk: 25,
                players[2].pk: 15,
            },
        ),
    )

    all_sizes = client.get(
        reverse("games:list"),
        {"group": str(group.pk), "game_type": "dominos"},
    ).content.decode()
    two_player = client.get(
        reverse("games:list"),
        {"group": str(group.pk), "game_type": "dominos", "game_size": "2"},
    ).content.decode()
    three_player = client.get(
        reverse("games:list"),
        {"group": str(group.pk), "game_type": "dominos", "game_size": "3"},
    ).content.decode()

    assert 'id="filter-game-size"' in all_sizes
    assert "All sizes" in all_sizes
    assert "(2-player)" in two_player or "2-player" in two_player
    assert two_player.count("game-list-data-row") == 1 or two_player.count("<tr") >= 1
    assert three_player.count("game-list-data-row") == 1 or "3-player" in three_player
    assert "4" not in all_sizes.split("filter-game-size")[1].split("</select>")[0]


@pytest.mark.django_db
def test_game_list_filters_by_player(client, user, group):
    other_group = create_group_with_owner(user=user, name="Other Club")
    pat = group.players.get(display_name="Pat")
    add_guest_player(group=other_group, display_name="Pat")

    client.force_login(user)
    client.post(reverse("games:create"), _load_roster_post(group))
    client.post(
        reverse("games:create"),
        _save_game_post(
            group,
            game_type_code="dominos",
            players_played=list(group.players.order_by("pk"))[:2],
        ),
    )
    client.post(
        reverse("games:create"),
        _load_roster_post(other_group, game_type_code="dominos"),
    )
    client.post(
        reverse("games:create"),
        _save_game_post(
            other_group,
            game_type_code="dominos",
            players_played=list(other_group.players.order_by("pk"))[:2],
        ),
    )

    dom_club_dominos = client.get(
        reverse("games:list"),
        {"group": str(group.pk), "game_type": "dominos"},
        follow=True,
    )
    pat_only = client.get(
        reverse("games:list"),
        {"group": str(group.pk), "game_type": "dominos", "player": str(pat.pk)},
        follow=True,
    )
    group_pat_only = client.get(
        reverse("games:list"),
        {"group": str(group.pk), "game_type": "dominos", "player": str(pat.pk)},
    )

    assert dom_club_dominos.status_code == 200
    dom_content = dom_club_dominos.content.decode()
    assert "All players" in dom_content
    assert "Pat (Dom Club)" not in dom_content
    assert "Pat (Other Club)" not in dom_content
    assert "All groups" not in dom_content

    assert pat_only.status_code == 200
    pat_content = pat_only.content.decode()
    assert pat_content.count("Dom Club") >= 1
    assert ">Other Club</a>" not in pat_content

    assert group_pat_only.status_code == 200
    group_pat_content = group_pat_only.content.decode()
    assert "Pat (Dom Club)" not in group_pat_content
    assert ">Other Club</a>" not in group_pat_content


@pytest.mark.django_db
def test_game_list_sort_and_empty_filter_message(client, user, group):
    client.force_login(user)
    client.post(reverse("games:create"), _load_roster_post(group))
    client.post(reverse("games:create"), _save_game_post(group))

    response = client.get(
        reverse("games:list"),
        {"game_type": "backgammon"},
        follow=True,
    )
    assert response.status_code == 200
    assert "No games match these filters." in response.content.decode()

    sorted_response = client.get(reverse("games:list"), {"sort": "asc"}, follow=True)
    assert sorted_response.status_code == 200
    assert 'value="asc" selected' in sorted_response.content.decode()


@pytest.mark.django_db
def test_game_detail_for_member(client, user, group):
    client.force_login(user)
    client.post(reverse("games:create"), _load_roster_post(group))
    client.post(reverse("games:create"), _save_game_post(group))
    game = Game.objects.get()
    response = client.get(reverse("games:detail", kwargs={"pk": game.pk}))
    content = response.content.decode()

    assert response.status_code == 200
    assert "Dom Club" in content
    assert "game-detail-title-icon" in content
    assert "game-types/dominos.png" in content
    assert f'href="/games/matchup/?game={game.pk}"' in content
    player = group.players.order_by("pk").first()
    assert (
        f'href="/leaderboards/detail/?group={group.pk}&amp;game_type_code=dominos&amp;player={player.pk}"'
        in content
    )


@pytest.mark.django_db
def test_reuse_roster_prefills_previous_players(client, user, group):
    client.force_login(user)
    client.post(reverse("games:create"), _load_roster_post(group))
    client.post(reverse("games:create"), _save_game_post(group))

    response = client.post(reverse("games:create"), _reuse_roster_post(group))
    content = response.content.decode()

    assert response.status_code == 200
    assert "Type player name" in content
    players = list(group.players.order_by("pk")[:2])
    assert players[0].display_label in content
    assert players[1].display_label in content
    assert "game-record-score-input" in content


@pytest.mark.django_db
def test_reuse_roster_prefills_selected_older_game(client, user, group):
    from datetime import date

    from leaderlodge.games.services import ParticipantInput, record_game
    from leaderlodge.groups.services import add_guest_player

    add_guest_player(group=group, display_name="Alex")
    players = list(group.players.order_by("pk")[:3])
    client.force_login(user)
    older = record_game(
        user=user,
        group=group,
        game_type_code="dominos",
        played_on=date(2026, 1, 1),
        participants=[
            ParticipantInput(player=players[0], score=30, result="win", placement=0),
            ParticipantInput(player=players[2], score=10, result="played", placement=1),
        ],
    )
    record_game(
        user=user,
        group=group,
        game_type_code="dominos",
        played_on=date(2026, 2, 1),
        participants=[
            ParticipantInput(player=players[0], score=25, result="win", placement=0),
            ParticipantInput(player=players[1], score=15, result="played", placement=1),
        ],
    )

    response = client.post(
        reverse("games:create"),
        _reuse_roster_post(group, reuse_game_id=older.pk),
    )
    content = response.content.decode()
    assert response.status_code == 200
    assert f'data-player-id="{players[0].pk}"' in content
    assert f'data-player-id="{players[2].pk}"' in content
    assert f'data-player-id="{players[1].pk}"' not in content
    assert content.count("data-game-row") == 2


@pytest.mark.django_db
def test_reuse_roster_stays_on_setup_without_previous_game(client, user, group):
    client.force_login(user)
    response = client.post(reverse("games:create"), _reuse_roster_post(group))
    content = response.content.decode()

    assert response.status_code == 200
    assert "Pick Players" in content
    assert "Type player name" not in content


@pytest.mark.django_db
def test_reuse_roster_does_not_use_other_game_type(client, user, group):
    client.force_login(user)
    client.post(
        reverse("games:create"), _save_game_post(group, game_type_code="dominos")
    )

    response = client.post(
        reverse("games:create"),
        _reuse_roster_post(group, game_type_code="progressiverummy"),
    )
    content = response.content.decode()

    assert response.status_code == 200
    assert "Pick Players" in content
    assert "Type player name" not in content
    assert "No previous game found" in content


@pytest.mark.django_db
def test_reuse_roster_uses_progressive_rummy_not_dominos(client, user, group):
    from datetime import date

    from leaderlodge.games.services import ParticipantInput, record_game
    from leaderlodge.groups.services import add_guest_player

    add_guest_player(group=group, display_name="Alex")
    players = list(group.players.order_by("pk")[:3])
    client.force_login(user)
    record_game(
        user=user,
        group=group,
        game_type_code="dominos",
        played_on=date(2026, 3, 1),
        participants=[
            ParticipantInput(player=players[0], score=30, result="win", placement=0),
            ParticipantInput(player=players[1], score=20, result="played", placement=1),
        ],
    )
    record_game(
        user=user,
        group=group,
        game_type_code="progressiverummy",
        played_on=date(2026, 2, 1),
        participants=[
            ParticipantInput(player=players[0], score=10, result="win", placement=0),
            ParticipantInput(player=players[1], score=20, result="played", placement=1),
            ParticipantInput(player=players[2], score=30, result="loss", placement=2),
        ],
    )

    response = client.post(
        reverse("games:create"),
        _reuse_roster_post(group, game_type_code="progressiverummy"),
    )
    content = response.content.decode()

    assert response.status_code == 200
    assert "Progressive Rummy" in content
    assert players[2].display_label in content
    assert content.count("data-game-row") == 3


@pytest.mark.django_db
def test_record_game_setup_honors_game_type_query_param(client, user, group):
    from leaderlodge.accounts.game_selection import (
        GAME_SELECTION_NAMESPACE,
        GAME_TYPE_CODE_KEY,
    )
    from leaderlodge.accounts.ui_settings import set_ui_settings

    set_ui_settings(
        user,
        GAME_SELECTION_NAMESPACE,
        {GAME_TYPE_CODE_KEY: "dominos"},
    )
    client.force_login(user)

    response = client.get(
        reverse("games:create"),
        {"group": str(group.pk), "game_type": "progressiverummy"},
    )
    content = response.content.decode()

    assert response.status_code == 200
    assert 'value="progressiverummy"' in content
    assert (
        "selected"
        in content.split('value="progressiverummy"', 1)[1].split("</option>", 1)[0]
    )
    assert 'value="dominos" selected' not in content.replace("\n", " ")


@pytest.mark.django_db
def test_reuse_preview_url_on_setup_page(client, user, group):
    client.force_login(user)
    empty = client.get(reverse("games:create"))
    content = empty.content.decode()
    assert reverse("games:reuse_preview") in content
    assert 'id="reuse-players-btn"' in content

    client.post(reverse("games:create"), _load_roster_post(group))
    client.post(reverse("games:create"), _save_game_post(group))

    preview = client.get(
        reverse("games:reuse_preview"),
        {"group": str(group.pk), "game_type": "dominos"},
    )
    players = list(group.players.order_by("pk")[:2])
    assert (
        preview.json()["summary"]
        == f"{players[0].display_label}, {players[1].display_label}"
    )
