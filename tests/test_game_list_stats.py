import pytest
from datetime import date
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone

from leaderlodge.games.list_stats import (
    STAT_CELL_BEST,
    STAT_CELL_TIE,
    STAT_CELL_WORST,
    GameListStatCell,
    _build_stat_rows,
    _highlight_extremes,
    _highlight_most_ties,
    _format_dates_summary,
    _humanize_date_range,
    _merge_equal_player_cells,
    build_game_list_stats,
)
from leaderlodge.games.models import Game, GameParticipantResult
from leaderlodge.games.registry import get_game_type
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


def _record_game(group, *, game_type_code="dominos", scores=None, location_name="", played_on=None):
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
        played_on=played_on or timezone.localdate(),
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
def test_game_list_stats_hides_all_column_for_two_players(client, user, group):
    client.force_login(user)
    players = _players_pair(group)
    _record_game(group, scores={players[0].pk: 30, players[1].pk: 20})

    response = client.get(
        reverse("games:list"),
        {"group": str(group.pk), "game_type": "dominos"},
    )
    content = response.content.decode()

    assert response.status_code == 200
    stats_table = content.split("game-list-stats-table", 1)[1].split("</table>", 1)[0]
    assert ">All<" not in stats_table
    assert "game-list-stats-col--all" not in stats_table


@pytest.mark.django_db
def test_game_list_stats_shows_all_column_for_three_players(client, user, group):
    from leaderlodge.games.services import ParticipantInput, record_game

    client.force_login(user)
    players = list(group.players.order_by("pk"))
    while len(players) < 3:
        players.append(add_guest_player(group=group, display_name=f"Guest{len(players)}"))
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
                score=30,
                result=GameParticipantResult.Result.LOSS,
                placement=3,
            ),
        ],
    )

    response = client.get(
        reverse("games:list"),
        {"group": str(group.pk), "game_type": "progressiverummy"},
    )
    content = response.content.decode()

    assert response.status_code == 200
    stats_table = content.split("game-list-stats-table", 1)[1].split("</table>", 1)[0]
    assert ">All<" in stats_table
    assert "game-list-stats-col--all" in stats_table


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


def test_highlight_extremes_marks_best_and_worst():
    assert _highlight_extremes([3, 1, 2], higher_is_best=True) == [
        STAT_CELL_BEST,
        STAT_CELL_WORST,
        "",
    ]
    assert _highlight_extremes([10, 40, 25], higher_is_best=False) == [
        STAT_CELL_BEST,
        STAT_CELL_WORST,
        "",
    ]
    assert _highlight_extremes([5, 5], higher_is_best=True) == ["", ""]


def test_highlight_most_ties_marks_highest_only():
    assert _highlight_most_ties([0, 0]) == ["", ""]
    assert _highlight_most_ties([1, 3, 3]) == ["", STAT_CELL_TIE, STAT_CELL_TIE]


def test_merge_equal_player_cells_combines_two_player_ties():
    cells = (
        GameListStatCell(value=2, css_class=STAT_CELL_TIE),
        GameListStatCell(value=2, css_class=STAT_CELL_TIE),
    )
    merged = _merge_equal_player_cells(cells)

    assert len(merged) == 1
    assert merged[0].value == 2
    assert merged[0].css_class == STAT_CELL_TIE
    assert merged[0].colspan == 2


def test_merge_equal_player_cells_skips_when_values_differ():
    cells = (
        GameListStatCell(value=1, css_class=STAT_CELL_TIE),
        GameListStatCell(value=2, css_class=STAT_CELL_TIE),
    )
    assert _merge_equal_player_cells(cells) == cells


def test_format_dates_summary():
    assert _format_dates_summary(
        date(2014, 2, 25),
        date(2026, 6, 15),
    ) == "Feb 25, 2014 - Jun 15, 2026 (12 years)"
    assert _format_dates_summary(
        date(2026, 2, 25),
        date(2026, 3, 2),
    ) == "Feb 25 - Mar 2, 2026 (5 days)"
    assert _format_dates_summary(
        date(2026, 2, 25),
        date(2026, 2, 25),
    ) == "Feb 25, 2026 (Same day)"


def test_humanize_date_range():
    assert _humanize_date_range(
        timezone.localdate(),
        timezone.localdate(),
    ) == "Same day"
    assert _humanize_date_range(
        date(2026, 1, 1),
        date(2026, 1, 8),
    ) == "1 week"
    assert _humanize_date_range(
        date(2026, 1, 1),
        date(2026, 4, 1),
    ) == "3 months"


@pytest.mark.django_db
def test_build_stat_rows_highlights_dominos_scores(user, group):
    players = _players_pair(group)
    _record_game(group, scores={players[0].pk: 30, players[1].pk: 20})
    _record_game(group, scores={players[0].pk: 30, players[1].pk: 20})
    _record_game(group, scores={players[0].pk: 25, players[1].pk: 25})
    _record_game(group, scores={players[0].pk: 10, players[1].pk: 40})

    params = {"group": str(group.pk), "game_type": "dominos", "location": "", "sort": "desc"}
    games_qs = _filtered_games_queryset(user, params)
    stats = build_game_list_stats(games_qs=games_qs, game_type_code="dominos")

    rows = {row.label: row for row in stats.rows}
    owner = group.players.get(linked_user=user)
    pat = group.players.get(display_name="Pat")

    assert rows["Total games"].global_cell is None
    assert len(rows["Total games"].player_cells) == 1
    assert rows["Total games"].player_cells[0].value == 4
    assert rows["Total games"].player_cells[0].colspan == 2
    assert rows["Total games"].player_cells[0].css_class == ""

    wins_by_player = {
        player.player.pk: cell.css_class
        for player, cell in zip(stats.players, rows["Wins"].player_cells, strict=True)
    }
    assert wins_by_player[owner.pk] == STAT_CELL_BEST
    assert wins_by_player[pat.pk] == STAT_CELL_WORST

    tie_row = rows["Ties"]
    assert len(tie_row.player_cells) == 1
    assert tie_row.player_cells[0].value == 1
    assert tie_row.player_cells[0].css_class == STAT_CELL_TIE
    assert tie_row.player_cells[0].colspan == 2

    points_by_player = {
        player.player.pk: cell.css_class
        for player, cell in zip(stats.players, rows["Total points"].player_cells, strict=True)
    }
    assert points_by_player[owner.pk] == STAT_CELL_WORST
    assert points_by_player[pat.pk] == STAT_CELL_BEST

    high_by_player = {
        player.player.pk: cell.css_class
        for player, cell in zip(stats.players, rows["High score"].player_cells, strict=True)
    }
    assert high_by_player[owner.pk] == STAT_CELL_WORST
    assert high_by_player[pat.pk] == STAT_CELL_BEST

    low_by_player = {
        player.player.pk: cell.css_class
        for player, cell in zip(stats.players, rows["Low score"].player_cells, strict=True)
    }
    assert low_by_player[owner.pk] == STAT_CELL_WORST
    assert low_by_player[pat.pk] == STAT_CELL_BEST


@pytest.mark.django_db
def test_build_stat_rows_highlights_progressive_rummy_losses_and_low_scores(user, group):
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
                score=30,
                result=GameParticipantResult.Result.LOSS,
                placement=3,
            ),
        ],
    )

    player_stats = tuple(
        build_game_list_stats(
            games_qs=_filtered_games_queryset(
                user,
                {
                    "group": str(group.pk),
                    "game_type": "progressiverummy",
                    "location": "",
                    "sort": "desc",
                },
            ),
            game_type_code="progressiverummy",
        ).players
    )
    rows = _build_stat_rows(
        players=player_stats,
        total_games=1,
        show_losses=True,
        score_direction=get_game_type("progressiverummy").score_direction,
        global_max_score=30,
        global_min_score=10,
    )
    rows_by_label = {row.label: row for row in rows}
    winner = players[0]
    loser_one = players[1]
    loser_two = players[2]

    def classes_for_row(label):
        return {
            player_stat.player.pk: cell.css_class
            for player_stat, cell in zip(player_stats, rows_by_label[label].player_cells, strict=True)
        }

    losses = classes_for_row("Losses")
    assert losses[winner.pk] == STAT_CELL_BEST
    assert losses[loser_one.pk] == STAT_CELL_WORST
    assert losses[loser_two.pk] == STAT_CELL_WORST

    points = classes_for_row("Total points")
    assert points[winner.pk] == STAT_CELL_BEST
    assert points[loser_two.pk] == STAT_CELL_WORST


@pytest.mark.django_db
def test_build_stat_rows_highlights_games_played_when_unequal(user, group):
    players = list(group.players.order_by("pk"))
    while len(players) < 3:
        players.append(add_guest_player(group=group, display_name=f"Guest{len(players)}"))

    from leaderlodge.games.scoring import assign_results_from_scores
    from leaderlodge.games.services import ParticipantInput, record_game

    for scores in ({players[0].pk: 30, players[1].pk: 20, players[2].pk: 10},):
        rows = [
            {"player": player, "score": scores[player.pk]}
            for player in players
        ]
        assign_results_from_scores(rows, "progressiverummy")
        record_game(
            user=group.created_by,
            group=group,
            game_type_code="progressiverummy",
            played_on=timezone.localdate(),
            participants=[
                ParticipantInput(
                    player=row["player"],
                    score=row["score"],
                    result=row["result"],
                    placement=row["placement"],
                )
                for row in rows
            ],
        )

    two_player_rows = [
        {"player": players[0], "score": 15},
        {"player": players[1], "score": 25},
    ]
    assign_results_from_scores(two_player_rows, "progressiverummy")
    record_game(
        user=group.created_by,
        group=group,
        game_type_code="progressiverummy",
        played_on=timezone.localdate(),
        participants=[
            ParticipantInput(
                player=row["player"],
                score=row["score"],
                result=row["result"],
                placement=row["placement"],
            )
            for row in two_player_rows
        ],
    )

    stats = build_game_list_stats(
        games_qs=_filtered_games_queryset(
            user,
            {
                "group": str(group.pk),
                "game_type": "progressiverummy",
                "location": "",
                "sort": "desc",
            },
        ),
        game_type_code="progressiverummy",
    )
    games_row = next(row for row in stats.rows if row.label == "Total games")
    games_by_player = {
        player_stat.player.pk: cell
        for player_stat, cell in zip(stats.players, games_row.player_cells, strict=True)
    }

    assert games_row.global_cell.value == 2
    assert games_by_player[players[0].pk].value == 2
    assert games_by_player[players[1].pk].value == 2
    assert games_by_player[players[2].pk].value == 1
    assert games_by_player[players[0].pk].css_class == STAT_CELL_BEST
    assert games_by_player[players[1].pk].css_class == STAT_CELL_BEST
    assert games_by_player[players[2].pk].css_class == STAT_CELL_WORST


@pytest.mark.django_db
def test_build_game_list_stats_excludes_players_hidden_from_game_list(user, group):
    players = list(group.players.order_by("pk"))
    while len(players) < 3:
        players.append(add_guest_player(group=group, display_name=f"Guest{len(players)}"))

    hidden = players[2]
    hidden.hide_from_game_list = True
    hidden.save(update_fields=["hide_from_game_list"])

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
                score=30,
                result=GameParticipantResult.Result.LOSS,
                placement=3,
            ),
        ],
    )

    games_qs = Game.objects.filter(group=group, game_type_code="progressiverummy")
    stats = build_game_list_stats(games_qs=games_qs, game_type_code="progressiverummy")

    assert len(stats.players) == 2
    assert {item.player.pk for item in stats.players} == {players[0].pk, players[1].pk}


@pytest.mark.django_db
def test_game_list_stats_table_hides_player_but_game_table_keeps_them(client, user, group):
    from leaderlodge.games.services import ParticipantInput, record_game

    client.force_login(user)
    players = list(group.players.order_by("pk"))
    while len(players) < 3:
        players.append(add_guest_player(group=group, display_name=f"Guest{len(players)}"))

    hidden = players[2]
    hidden.display_name = "Allyn"
    hidden.hide_from_game_list = True
    hidden.save(update_fields=["display_name", "hide_from_game_list"])

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
                score=30,
                result=GameParticipantResult.Result.LOSS,
                placement=3,
            ),
        ],
    )

    response = client.get(
        reverse("games:list"),
        {"group": str(group.pk), "game_type": "progressiverummy"},
    )
    content = response.content.decode()

    assert response.status_code == 200
    stats_table = content.split("game-list-stats-table", 1)[1].split("</table>", 1)[0]
    game_table = content.split("game-list-table game-list-data-table", 1)[1].split("</table>", 1)[0]

    assert "Allyn" not in stats_table
    assert "Allyn" in game_table


@pytest.mark.django_db
def test_build_game_list_stats_includes_date_rows(user, group):
    players = _players_pair(group)
    _record_game(
        group,
        scores={players[0].pk: 30, players[1].pk: 20},
        played_on=date(2026, 1, 5),
    )
    _record_game(
        group,
        scores={players[0].pk: 25, players[1].pk: 25},
        played_on=date(2026, 3, 15),
    )

    stats = build_game_list_stats(
        games_qs=_filtered_games_queryset(
            user,
            {"group": str(group.pk), "game_type": "dominos", "location": "", "sort": "desc"},
        ),
        game_type_code="dominos",
    )
    rows = {row.label: row for row in stats.rows}

    assert rows["Date Range"].player_cells[0].value == "Jan 5 - Mar 15, 2026 (2 months)"
    assert rows["Date Range"].player_cells[0].colspan == 2
