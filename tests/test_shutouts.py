import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone

from leaderlodge.games.models import GameParticipantResult
from leaderlodge.games.scoring import assign_results_from_scores
from leaderlodge.games.services import ParticipantInput, record_game
from leaderlodge.games.shutouts import (
    is_shutout_game,
    shutout_counts_by_player,
    shutout_game_ids,
)
from leaderlodge.groups.services import add_guest_player, create_group_with_owner
from leaderlodge.groups.teams import resolve_side_player
from leaderlodge.insights.tools.executor import AskScope, ToolExecutor
from leaderlodge.insights.tools.standings import list_game_types, query_player_detail
from leaderlodge.leaderboards.game_filters import (
    LeaderboardGameFilters,
    apply_game_filters_to_results_qs,
    resolve_leaderboard_game_filters,
)
from leaderlodge.leaderboards.period import LeaderboardPeriod
from leaderlodge.leaderboards.service import get_player_rank_detail, get_player_rankings


@pytest.fixture
def user(db):
    return User.objects.create_user(username="david", password="test-pass-123")


@pytest.fixture
def group(user):
    group = create_group_with_owner(user=user, name="Pickle Club")
    add_guest_player(group=group, display_name="Pat")
    add_guest_player(group=group, display_name="Quinn")
    add_guest_player(group=group, display_name="Riley")
    return group


def _mock_results(game_id, *sides):
    """Build minimal result rows: (player_id, score, result)."""
    rows = []
    for player_id, score, result in sides:
        row = type(
            "ResultRow",
            (),
            {
                "game_id": game_id,
                "player_id": player_id,
                "score": score,
                "result": result,
            },
        )()
        rows.append(row)
    return rows


@pytest.mark.parametrize(
    "sides,expected",
    [
        (((1, 10, "win"), (2, 0, "played")), True),
        (((1, 10, "win"), (2, 0, "played"), (3, 0, "played")), True),
        (
            ((1, 10, "win"), (2, 0, "played"), (3, 0, "played"), (4, 0, "played")),
            True,
        ),
        (((1, 10, "win"), (2, 0, "played"), (3, 1, "played")), False),
        (((1, 10, "win"), (2, 5, "played"), (3, 0, "played")), False),
        (
            ((1, 10, "win"), (2, 3, "played"), (3, 4, "played"), (4, 0, "played")),
            False,
        ),
    ],
)
def test_is_shutout_game_multi_side_rules(sides, expected):
    win = GameParticipantResult.Result.WIN
    played = GameParticipantResult.Result.PLAYED
    normalized = []
    for side in sides:
        player_id, score, result_name = side
        result = win if result_name == "win" else played
        normalized.append((player_id, score, result))
    results = _mock_results(1, *normalized)
    assert is_shutout_game("pickleball", results) is expected


@pytest.mark.parametrize("game_type_code", ["dominos", "progressiverummy"])
def test_is_shutout_game_rejects_non_shutout_types(game_type_code):
    win = GameParticipantResult.Result.WIN
    played = GameParticipantResult.Result.PLAYED
    results = _mock_results(1, (1, 10, win), (2, 0, played))
    assert is_shutout_game(game_type_code, results) is False


def _record_pickleball(user, group, *, participants):
    return record_game(
        user=user,
        group=group,
        game_type_code="pickleball",
        played_on=timezone.localdate(),
        participants=participants,
    )


@pytest.mark.django_db
def test_shutout_counts_credit_team_entity_only(group, user):
    players = list(group.players.order_by("pk"))
    owner, pat, quinn = players[:3]
    team = resolve_side_player(group=group, members=[owner, pat])

    rows = [
        {"player": team, "score": 11},
        {"player": quinn, "score": 0},
    ]
    assign_results_from_scores(rows, "pickleball")
    _record_pickleball(
        user,
        group,
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

    from leaderlodge.games.models import GameParticipantResult

    results = list(
        GameParticipantResult.objects.filter(game__group=group).select_related("game")
    )
    counts = shutout_counts_by_player("pickleball", results)
    assert counts.get(team.pk) == 1.0
    assert owner.pk not in counts
    assert pat.pk not in counts


@pytest.mark.django_db
def test_shutout_only_filter_credits_pickled_wins_to_team_entity_only(group, user):
    players = list(group.players.order_by("pk"))
    owner, pat, quinn = players[:3]
    team = resolve_side_player(group=group, members=[owner, pat])

    def record_team_shutout():
        rows = [
            {"player": team, "score": 11},
            {"player": quinn, "score": 0},
        ]
        assign_results_from_scores(rows, "pickleball")
        _record_pickleball(
            user,
            group,
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

    record_team_shutout()
    record_team_shutout()

    rankings = get_player_rankings(
        group,
        game_type_code="pickleball",
        game_filters=LeaderboardGameFilters(shutout_only=True),
    )
    by_label = {row.player.display_label: row for row in rankings}
    assert by_label[team.display_name].wins == 2.0
    assert by_label[owner.display_label].wins == 0.0
    assert by_label["Pat"].wins == 0.0


@pytest.mark.django_db
def test_shutout_filter_scopes_standings_to_shutout_games(group, user):
    players = list(group.players.order_by("pk"))

    def record(*, winner_idx, loser_score):
        rows = [
            {"player": players[winner_idx], "score": 11},
            {"player": players[1 - winner_idx], "score": loser_score},
        ]
        assign_results_from_scores(rows, "pickleball")
        _record_pickleball(
            user,
            group,
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

    record(winner_idx=0, loser_score=0)
    record(winner_idx=1, loser_score=7)

    all_rankings = get_player_rankings(group, game_type_code="pickleball")
    pickle_only = get_player_rankings(
        group,
        game_type_code="pickleball",
        game_filters=LeaderboardGameFilters(shutout_only=True),
    )
    assert len(all_rankings) == 2
    assert len(pickle_only) == 2
    shutout_winner = next(row for row in pickle_only if row.wins == 1.0)
    shutout_loser = next(row for row in pickle_only if row.player.pk == players[1].pk)
    assert shutout_winner.games_played == 1.0
    assert shutout_loser.games_played == 1.0
    assert shutout_loser.wins == 0.0

    winner = players[0]
    detail = get_player_rank_detail(
        group,
        winner,
        game_type_code="pickleball",
        game_filters=LeaderboardGameFilters(shutout_only=True),
    )
    assert detail is not None
    assert detail.ranking.games_played == 1.0
    assert detail.ranking.wins == 1.0


@pytest.mark.django_db
def test_shutouts_do_not_affect_rank_score(group, user):
    players = list(group.players.order_by("pk"))

    def record(*, winner_idx, loser_score):
        rows = [
            {"player": players[winner_idx], "score": 11},
            {"player": players[1 - winner_idx], "score": loser_score},
        ]
        assign_results_from_scores(rows, "pickleball")
        _record_pickleball(
            user,
            group,
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

    record(winner_idx=0, loser_score=0)
    record(winner_idx=0, loser_score=7)

    rankings = get_player_rankings(group, game_type_code="pickleball")
    winner_row = next(row for row in rankings if row.player.pk == players[0].pk)
    assert winner_row.games_played == 2.0
    assert winner_row.wins == 2.0


@pytest.mark.django_db
def test_leaderboard_page_omits_shutout_filter_and_column(client, user, group):
    players = list(group.players.order_by("pk"))
    rows = [
        {"player": players[0], "score": 11},
        {"player": players[1], "score": 0},
    ]
    assign_results_from_scores(rows, "pickleball")
    _record_pickleball(
        user,
        group,
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

    client.force_login(user)
    response = client.get(
        reverse("leaderboards:index"),
        {"group": str(group.pk), "game_type_code": "pickleball"},
    )
    content = response.content.decode()
    assert response.status_code == 200
    assert 'name="shutout"' not in content
    assert 'id="leaderboard-shutout-only"' not in content
    assert ">Pickled</th>" not in content


@pytest.mark.django_db
def test_game_list_shows_shutout_icon(client, user, group):
    players = list(group.players.order_by("pk"))
    rows = [
        {"player": players[0], "score": 11},
        {"player": players[1], "score": 0},
    ]
    assign_results_from_scores(rows, "pickleball")
    _record_pickleball(
        user,
        group,
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

    client.force_login(user)
    response = client.get(
        reverse("games:list"),
        {"group": str(group.pk), "game_type": "pickleball"},
    )
    content = response.content.decode()
    assert response.status_code == 200
    assert "game-types/pickle.png" in content
    assert 'name="shutout"' in content


@pytest.mark.django_db
def test_game_detail_shows_shutout_icon_on_winner(client, user, group):
    players = list(group.players.order_by("pk"))
    rows = [
        {"player": players[0], "score": 11},
        {"player": players[1], "score": 0},
    ]
    assign_results_from_scores(rows, "pickleball")
    game = record_game(
        user=user,
        group=group,
        game_type_code="pickleball",
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

    client.force_login(user)
    response = client.get(reverse("games:detail", kwargs={"pk": game.pk}))
    content = response.content.decode()
    assert response.status_code == 200
    assert "result-badge--shutout" not in content
    assert "game-detail-result-shutout-icon" in content
    assert "game-types/pickle.png" in content
    assert content.count("game-detail-result-shutout-icon") == 1


@pytest.mark.django_db
def test_ask_tools_support_shutout_filter(user, group):
    players = list(group.players.order_by("pk"))
    rows = [
        {"player": players[0], "score": 11},
        {"player": players[1], "score": 0},
    ]
    assign_results_from_scores(rows, "pickleball")
    _record_pickleball(
        user,
        group,
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

    catalog = list_game_types(group)
    pickleball = next(
        item for item in catalog["game_types"] if item["code"] == "pickleball"
    )
    assert pickleball["shutout"]["key"] == "shutout_only"
    assert pickleball["shutout"]["title"] == "Pickled"
    assert "pickled" in pickleball["shutout"]["ask_aliases"]

    scope = AskScope(
        group=group,
        period=LeaderboardPeriod.all_time(),
        default_game_type_code="pickleball",
        available_game_type_codes=("pickleball",),
    )
    executor = ToolExecutor(scope)
    leaderboard = executor.execute(
        "query_leaderboard",
        {"game_type_code": "pickleball", "shutout_only": True, "all_time": True},
    )
    assert leaderboard["game_features"] == [
        {
            "key": "shutout_only",
            "title": "Pickled",
            "value_code": "1",
            "value_label": "Pickled",
        }
    ]
    assert len(leaderboard["rankings"]) == 2
    shutout_winner = next(row for row in leaderboard["rankings"] if row["wins"] == 1.0)
    assert shutout_winner["games_played"] == 1.0
    assert "shutout_wins" in shutout_winner
    assert shutout_winner["shutout_wins"] == 1.0

    detail = query_player_detail(
        group,
        player_id=players[0].pk,
        game_type_code="pickleball",
        game_filters=LeaderboardGameFilters(shutout_only=True),
    )
    assert detail["games_played"] == 1.0
    assert detail["wins"] == 1.0
    assert "shutout_label" not in detail
    assert "shutout_count" not in detail


@pytest.mark.django_db
def test_without_shutout_scope():
    scoped = LeaderboardGameFilters(score_type="rally", shutout_only=True)
    stripped = scoped.without_shutout_scope()
    assert stripped.shutout_only is False
    assert stripped.score_type == "rally"


@pytest.mark.django_db
def test_resolve_leaderboard_game_filters_shutout_only(group):
    filters = resolve_leaderboard_game_filters(
        {"shutout": "1"},
        game_type_code="pickleball",
    )
    assert filters.shutout_only is True

    dominos_filters = resolve_leaderboard_game_filters(
        {"shutout": "1"},
        game_type_code="dominos",
    )
    assert dominos_filters.shutout_only is False


@pytest.mark.django_db
def test_shutout_game_ids_from_results_qs(group, user):
    players = list(group.players.order_by("pk"))

    def record(*, winner_idx, loser_score):
        rows = [
            {"player": players[winner_idx], "score": 11},
            {"player": players[1 - winner_idx], "score": loser_score},
        ]
        assign_results_from_scores(rows, "pickleball")
        return _record_pickleball(
            user,
            group,
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

    shutout_game = record(winner_idx=0, loser_score=0)
    record(winner_idx=1, loser_score=5)

    from leaderlodge.games.models import GameParticipantResult

    results_qs = GameParticipantResult.objects.filter(game__group=group)
    filtered = apply_game_filters_to_results_qs(
        results_qs,
        LeaderboardGameFilters(shutout_only=True),
        game_type_code="pickleball",
    )
    game_ids = set(filtered.values_list("game_id", flat=True))
    assert game_ids == {shutout_game.pk}

    all_results = list(results_qs.select_related("game"))
    assert shutout_game_ids("pickleball", all_results) == {shutout_game.pk}
