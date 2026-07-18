import pytest

from leaderlodge.games.scoring import assign_results_from_scores
from leaderlodge.games.services import ParticipantInput, record_game
from leaderlodge.groups.services import add_guest_player, create_group_with_owner
from leaderlodge.insights.tools.executor import AskScope, ToolExecutor
from leaderlodge.insights.tools.placements import query_placement_leaders
from leaderlodge.leaderboards.period import LeaderboardPeriod


@pytest.fixture
def user(db):
    from django.contrib.auth.models import User

    return User.objects.create_user(username="david", password="test-pass-123")


@pytest.fixture
def group(user):
    group = create_group_with_owner(user=user, name="Dom Club")
    add_guest_player(group=group, display_name="Pat")
    add_guest_player(group=group, display_name="Sam")
    return group


def _record_game(group, user, *, winner_idx=0, loser_idx=1, third_idx=2):
    players = list(group.players.order_by("pk"))
    rows = [
        {"player": players[winner_idx], "score": 35},
        {"player": players[loser_idx], "score": 20},
    ]
    if third_idx is not None and len(players) > 2:
        rows.append({"player": players[third_idx], "score": 15})
    assign_results_from_scores(rows, "dominos")
    participants = [
        ParticipantInput(
            player=row["player"],
            score=row["score"],
            result=row["result"],
            placement=row["placement"],
        )
        for row in rows
    ]
    record_game(
        user=user,
        group=group,
        game_type_code="dominos",
        played_on="2026-01-15",
        participants=participants,
    )


@pytest.mark.django_db
def test_query_placement_leaders_returns_second_place_counts(user, group):
    add_guest_player(group=group, display_name="Alex")
    _record_game(group, user, winner_idx=0, loser_idx=1, third_idx=2)
    _record_game(group, user, winner_idx=1, loser_idx=0, third_idx=2)

    result = query_placement_leaders(
        group,
        game_type_code="dominos",
        placement=1,
    )

    assert result["placement_label"] == "2nd"
    assert len(result["leaders"]) >= 1
    top = result["leaders"][0]
    assert top["weighted_count"] >= 1


def test_render_ask_user_message_includes_low_wins_hint():
    from leaderlodge.insights.prompts import render_ask_user_message

    message = render_ask_user_message(
        question="Who is leading?",
        group_name="Dom Club",
        game_type_code="progressiverummy",
        period_label="",
        player_roster=[],
    )

    assert "score_direction=low_wins" in message
    assert "lower raw game points are better" in message
    assert "rank_score is always higher-is-better" in message


@pytest.mark.django_db
def test_query_head_to_head_includes_score_direction(user, group):
    _record_game(group, user, winner_idx=0, loser_idx=1, third_idx=2)
    _record_game(group, user, winner_idx=1, loser_idx=0, third_idx=2)
    players = list(group.players.order_by("pk"))

    from leaderlodge.insights.tools.head_to_head import query_head_to_head

    result = query_head_to_head(
        group,
        game_type_code="dominos",
        player_a_id=players[0].pk,
        player_b_id=players[1].pk,
    )

    assert result["games_together"] == 2
    assert result["score_direction"] == "high_wins"
    assert result["player_a"]["rank"] >= 1
    assert result["player_a"]["rank_score"] is not None
    assert result["player_b"]["rank"] >= 1
    assert result["player_b"]["rank_score"] is not None
    assert result["player_a"]["win_pct"] > 0
    assert "wins_display" in result["player_a"]
    assert result["player_a"]["games_played"] == 2
    assert result["player_b"]["games_played"] == 2
    assert result["player_a"]["wins"] + result["player_b"]["wins"] == 2
    assert "total_points_display" in result["player_a"]
    assert "/game" in result["player_a"]["total_points_display"]


@pytest.mark.django_db
def test_tool_executor_all_time_overrides_scope_period(user, group):
    _record_game(group, user, third_idx=None)
    scope = AskScope(
        group=group,
        period=LeaderboardPeriod(year=2020),
        default_game_type_code="dominos",
        available_game_type_codes=("dominos",),
    )
    executor = ToolExecutor(scope)

    result = executor.execute(
        "query_leaderboard",
        {"game_type_code": "dominos", "all_time": True},
    )

    assert result["period"] == {"all_time": True}


@pytest.mark.django_db
def test_query_player_detail_includes_score_highlights(user, group):
    _record_game(group, user, third_idx=None)
    player = group.players.order_by("pk").first()
    from leaderlodge.insights.tools.standings import query_player_detail

    result = query_player_detail(
        group,
        player_id=player.pk,
        game_type_code="dominos",
    )

    assert result["best_score"] is not None
    assert result["win_pct"] >= 0
    assert result["wins_display"] == f"{int(result['wins'])} ({result['win_pct']}%)"
    assert "tie_pct" in result
    assert "loss_pct" in result
    assert result["podium_count"] >= 0
    assert result["date_range_label"]
    assert "avg_points_display" in result


@pytest.mark.django_db
def test_tool_executor_rejects_unknown_game_type(user, group):
    _record_game(group, user, third_idx=None)
    scope = AskScope(
        group=group,
        period=LeaderboardPeriod.all_time(),
        default_game_type_code="dominos",
        available_game_type_codes=("dominos",),
    )
    executor = ToolExecutor(scope)

    with pytest.raises(Exception, match="Game type not found"):
        executor.execute(
            "query_leaderboard",
            {"game_type_code": "mahjongg"},
        )


@pytest.mark.django_db
def test_query_loss_leaders_orders_by_losses(user, group):
    from datetime import date

    from leaderlodge.games.scoring import assign_results_from_scores
    from leaderlodge.games.services import ParticipantInput, record_game
    from leaderlodge.insights.tools.loss_leaders import query_loss_leaders

    players = list(group.players.order_by("pk"))
    while len(players) < 3:
        players.append(
            add_guest_player(group=group, display_name=f"Guest{len(players)}")
        )

    def record_pr(winner_idx=0):
        rows = [
            {"player": players[0], "score": 30},
            {"player": players[1], "score": 20},
            {"player": players[2], "score": 10},
        ]
        rows[winner_idx]["score"] = 0
        assign_results_from_scores(rows, "progressiverummy")
        record_game(
            user=user,
            group=group,
            game_type_code="progressiverummy",
            played_on=date(2026, 2, 1),
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

    record_pr(winner_idx=0)
    record_pr(winner_idx=0)
    record_pr(winner_idx=1)

    result = query_loss_leaders(group, game_type_code="progressiverummy", limit=5)
    assert result["supports_loser"] is True
    assert len(result["leaders"]) >= 1
    top = result["leaders"][0]
    assert top["losses"] >= 1
    assert "losses_display" in top


@pytest.mark.django_db
def test_query_loss_leaders_rejects_dominos(user, group):
    _record_game(group, user, third_idx=None)
    from leaderlodge.insights.tools.loss_leaders import query_loss_leaders

    result = query_loss_leaders(group, game_type_code="dominos")
    assert result["supports_loser"] is False
    assert "error" in result


@pytest.mark.django_db
def test_compare_players_returns_multiple_snapshots(user, group):
    _record_game(group, user, third_idx=None)
    players = list(group.players.order_by("pk")[:2])
    from leaderlodge.insights.tools.compare import compare_players

    result = compare_players(
        group,
        player_ids=[players[0].pk, players[1].pk],
        game_type_code="dominos",
    )

    assert len(result["players"]) == 2
    assert all(row.get("rank") is not None for row in result["players"])


@pytest.mark.django_db
def test_query_date_range_leaderboard_filters_games(user, group):
    from datetime import date

    from leaderlodge.games.scoring import assign_results_from_scores
    from leaderlodge.games.services import ParticipantInput, record_game
    from leaderlodge.insights.tools.standings import query_date_range_leaderboard

    players = list(group.players.order_by("pk")[:2])
    rows = [
        {"player": players[0], "score": 35},
        {"player": players[1], "score": 20},
    ]
    assign_results_from_scores(rows, "dominos")
    participants = [
        ParticipantInput(
            player=row["player"],
            score=row["score"],
            result=row["result"],
            placement=row["placement"],
        )
        for row in rows
    ]
    record_game(
        user=user,
        group=group,
        game_type_code="dominos",
        played_on=date(2026, 3, 10),
        participants=participants,
    )
    record_game(
        user=user,
        group=group,
        game_type_code="dominos",
        played_on=date(2026, 4, 10),
        participants=participants,
    )

    result = query_date_range_leaderboard(
        group,
        game_type_code="dominos",
        start_date=date(2026, 3, 1),
        end_date=date(2026, 3, 31),
    )

    assert result["start_date"] == "2026-03-01"
    assert len(result["rankings"]) >= 1
    assert result["rankings"][0]["games_played"] == 1


@pytest.mark.django_db
def test_query_date_range_leaderboard_accepts_period_preset(user, group):
    from datetime import date

    from leaderlodge.games.scoring import assign_results_from_scores
    from leaderlodge.games.services import ParticipantInput, record_game
    from leaderlodge.insights.tools.executor import ToolExecutor
    from leaderlodge.insights.tools.scope import AskScope
    from leaderlodge.leaderboards.period import LeaderboardPeriod

    players = list(group.players.order_by("pk")[:2])
    rows = [
        {"player": players[0], "score": 35},
        {"player": players[1], "score": 20},
    ]
    assign_results_from_scores(rows, "dominos")
    participants = [
        ParticipantInput(
            player=row["player"],
            score=row["score"],
            result=row["result"],
            placement=row["placement"],
        )
        for row in rows
    ]
    record_game(
        user=user,
        group=group,
        game_type_code="dominos",
        played_on=date.today(),
        participants=participants,
    )

    executor = ToolExecutor(
        AskScope(
            group=group,
            period=LeaderboardPeriod.all_time(),
            default_game_type_code="dominos",
            available_game_type_codes=("dominos",),
        )
    )
    result = executor.execute(
        "query_date_range_leaderboard",
        {"game_type_code": "dominos", "period_preset": "today"},
    )
    assert result["start_date"] == date.today().isoformat()
    assert result["end_date"] == date.today().isoformat()
    assert result["rankings"][0]["games_played"] == 1


@pytest.mark.django_db
def test_query_location_leaderboard_filters_by_venue(user, group):
    from datetime import date

    from leaderlodge.games.scoring import assign_results_from_scores
    from leaderlodge.games.services import ParticipantInput, record_game
    from leaderlodge.groups.locations import resolve_game_location
    from leaderlodge.insights.tools.standings import query_location_leaderboard

    location = resolve_game_location(group=group, location_name="Joe's House")
    players = list(group.players.order_by("pk")[:2])
    rows = [
        {"player": players[0], "score": 35},
        {"player": players[1], "score": 20},
    ]
    assign_results_from_scores(rows, "dominos")
    participants = [
        ParticipantInput(
            player=row["player"],
            score=row["score"],
            result=row["result"],
            placement=row["placement"],
        )
        for row in rows
    ]
    record_game(
        user=user,
        group=group,
        game_type_code="dominos",
        played_on=date(2026, 5, 1),
        location=location,
        participants=participants,
    )

    result = query_location_leaderboard(
        group,
        game_type_code="dominos",
        location_id=location.pk,
        location_name=location.name,
    )

    assert result["location_name"] == "Joe's House"
    assert len(result["rankings"]) >= 1


@pytest.mark.django_db
def test_query_region_leaderboard_aggregates_venues_in_state(user, group):
    from datetime import date

    from leaderlodge.groups.location_geo import (
        GEOCODE_SOURCE_PLACES_LOOKUP,
        LocationGeo,
    )
    from leaderlodge.groups.locations import get_or_create_location
    from leaderlodge.insights.tools.standings import query_region_leaderboard

    la = get_or_create_location(
        library=group.location_library,
        name="LA Spot",
        geo=LocationGeo(
            lat=34.05,
            lon=-118.25,
            city="Los Angeles",
            state="CA",
            geocode_source=GEOCODE_SOURCE_PLACES_LOOKUP,
        ),
    )
    sm = get_or_create_location(
        library=group.location_library,
        name="SM Spot",
        geo=LocationGeo(
            lat=34.01,
            lon=-118.49,
            city="Santa Monica",
            state="CA",
            geocode_source=GEOCODE_SOURCE_PLACES_LOOKUP,
        ),
    )
    other = get_or_create_location(
        library=group.location_library,
        name="NY Spot",
        geo=LocationGeo(
            lat=40.7,
            lon=-74.0,
            city="New York",
            state="NY",
            geocode_source=GEOCODE_SOURCE_PLACES_LOOKUP,
        ),
    )

    players = list(group.players.order_by("pk")[:2])
    for location in (la, sm, other):
        rows = [
            {"player": players[0], "score": 35},
            {"player": players[1], "score": 20},
        ]
        assign_results_from_scores(rows, "dominos")
        participants = [
            ParticipantInput(
                player=row["player"],
                score=row["score"],
                result=row["result"],
                placement=row["placement"],
            )
            for row in rows
        ]
        record_game(
            user=user,
            group=group,
            game_type_code="dominos",
            played_on=date(2026, 5, 1),
            location=location,
            participants=participants,
        )

    result = query_region_leaderboard(
        group,
        game_type_code="dominos",
        state="California",
    )

    assert result["state"] == "CA"
    assert result["matched_venue_count"] == 2
    assert {v["name"] for v in result["matched_venues"]} == {"LA Spot", "SM Spot"}
    assert result["rankings"][0]["games_played"] == 2


@pytest.mark.django_db
def test_query_region_leaderboard_filters_by_city(user, group):
    from datetime import date

    from leaderlodge.groups.location_geo import (
        GEOCODE_SOURCE_PLACES_LOOKUP,
        LocationGeo,
    )
    from leaderlodge.groups.locations import get_or_create_location
    from leaderlodge.insights.tools.standings import query_region_leaderboard

    sm = get_or_create_location(
        library=group.location_library,
        name="SM Spot",
        geo=LocationGeo(
            lat=34.01,
            lon=-118.49,
            city="Santa Monica",
            state="CA",
            geocode_source=GEOCODE_SOURCE_PLACES_LOOKUP,
        ),
    )
    la = get_or_create_location(
        library=group.location_library,
        name="LA Spot",
        geo=LocationGeo(
            lat=34.05,
            lon=-118.25,
            city="Los Angeles",
            state="CA",
            geocode_source=GEOCODE_SOURCE_PLACES_LOOKUP,
        ),
    )
    players = list(group.players.order_by("pk")[:2])
    for location in (sm, la):
        rows = [
            {"player": players[0], "score": 35},
            {"player": players[1], "score": 20},
        ]
        assign_results_from_scores(rows, "dominos")
        participants = [
            ParticipantInput(
                player=row["player"],
                score=row["score"],
                result=row["result"],
                placement=row["placement"],
            )
            for row in rows
        ]
        record_game(
            user=user,
            group=group,
            game_type_code="dominos",
            played_on=date(2026, 6, 1),
            location=location,
            participants=participants,
        )

    result = query_region_leaderboard(
        group,
        game_type_code="dominos",
        city="Santa Monica, CA",
    )

    assert result["city"] == "Santa Monica"
    assert result["state"] == "CA"
    assert result["matched_venue_count"] == 1
    assert result["rankings"][0]["games_played"] == 1


@pytest.mark.django_db
def test_query_region_leaderboard_exclude_state(user, group):
    from datetime import date

    from leaderlodge.groups.location_geo import (
        GEOCODE_SOURCE_PLACES_LOOKUP,
        LocationGeo,
    )
    from leaderlodge.groups.locations import get_or_create_location
    from leaderlodge.insights.tools.standings import query_region_leaderboard

    ca = get_or_create_location(
        library=group.location_library,
        name="LA Spot",
        geo=LocationGeo(
            lat=34.05,
            lon=-118.25,
            city="Los Angeles",
            state="CA",
            geocode_source=GEOCODE_SOURCE_PLACES_LOOKUP,
        ),
    )
    ny = get_or_create_location(
        library=group.location_library,
        name="NY Spot",
        geo=LocationGeo(
            lat=40.7,
            lon=-74.0,
            city="New York",
            state="NY",
            geocode_source=GEOCODE_SOURCE_PLACES_LOOKUP,
        ),
    )
    get_or_create_location(library=group.location_library, name="No Geo Spot")

    players = list(group.players.order_by("pk")[:2])
    for location in (ca, ny):
        rows = [
            {"player": players[0], "score": 35},
            {"player": players[1], "score": 20},
        ]
        assign_results_from_scores(rows, "dominos")
        participants = [
            ParticipantInput(
                player=row["player"],
                score=row["score"],
                result=row["result"],
                placement=row["placement"],
            )
            for row in rows
        ]
        record_game(
            user=user,
            group=group,
            game_type_code="dominos",
            played_on=date(2026, 5, 1),
            location=location,
            participants=participants,
        )

    result = query_region_leaderboard(
        group,
        game_type_code="dominos",
        state="California",
        exclude=True,
    )

    assert result["exclude"] is True
    assert result["region_label"] == "outside California"
    assert result["matched_venue_count"] == 1
    assert result["matched_venues"][0]["name"] == "NY Spot"
    assert result["rankings"][0]["games_played"] == 1


@pytest.mark.django_db
def test_query_play_locations_orders_by_game_count(user, group):
    from datetime import date

    from leaderlodge.groups.location_geo import (
        GEOCODE_SOURCE_PLACES_LOOKUP,
        LocationGeo,
    )
    from leaderlodge.groups.locations import get_or_create_location
    from leaderlodge.insights.tools.standings import query_play_locations

    busy = get_or_create_location(
        library=group.location_library,
        name="Busy Spot",
        geo=LocationGeo(
            lat=34.05,
            lon=-118.25,
            city="Los Angeles",
            state="CA",
            geocode_source=GEOCODE_SOURCE_PLACES_LOOKUP,
        ),
    )
    quiet = get_or_create_location(
        library=group.location_library,
        name="Quiet Spot",
        geo=LocationGeo(
            lat=34.01,
            lon=-118.49,
            city="Santa Monica",
            state="CA",
            geocode_source=GEOCODE_SOURCE_PLACES_LOOKUP,
        ),
    )
    players = list(group.players.order_by("pk")[:2])

    def _play(location, day):
        rows = [
            {"player": players[0], "score": 35},
            {"player": players[1], "score": 20},
        ]
        assign_results_from_scores(rows, "dominos")
        participants = [
            ParticipantInput(
                player=row["player"],
                score=row["score"],
                result=row["result"],
                placement=row["placement"],
            )
            for row in rows
        ]
        record_game(
            user=user,
            group=group,
            game_type_code="dominos",
            played_on=date(2026, 7, day),
            location=location,
            participants=participants,
        )

    _play(busy, 1)
    _play(busy, 2)
    _play(quiet, 3)

    result = query_play_locations(group, game_type_code="dominos")
    assert result["locations"][0]["name"] == "Busy Spot"
    assert result["locations"][0]["games_played"] == 2
    assert result["locations"][1]["name"] == "Quiet Spot"


@pytest.mark.django_db
def test_query_player_play_locations_by_state(user, group):
    from datetime import date

    from leaderlodge.groups.location_geo import (
        GEOCODE_SOURCE_PLACES_LOOKUP,
        LocationGeo,
    )
    from leaderlodge.groups.locations import get_or_create_location
    from leaderlodge.insights.tools.standings import query_player_play_locations

    ca = get_or_create_location(
        library=group.location_library,
        name="LA Spot",
        geo=LocationGeo(
            lat=34.05,
            lon=-118.25,
            city="Los Angeles",
            state="CA",
            geocode_source=GEOCODE_SOURCE_PLACES_LOOKUP,
        ),
    )
    ny = get_or_create_location(
        library=group.location_library,
        name="NY Spot",
        geo=LocationGeo(
            lat=40.7,
            lon=-74.0,
            city="New York",
            state="NY",
            geocode_source=GEOCODE_SOURCE_PLACES_LOOKUP,
        ),
    )
    blank = get_or_create_location(library=group.location_library, name="Home")
    players = list(group.players.order_by("pk")[:2])
    nancy = players[0]

    def _play(location, day):
        rows = [
            {"player": players[0], "score": 35},
            {"player": players[1], "score": 20},
        ]
        assign_results_from_scores(rows, "dominos")
        participants = [
            ParticipantInput(
                player=row["player"],
                score=row["score"],
                result=row["result"],
                placement=row["placement"],
            )
            for row in rows
        ]
        record_game(
            user=user,
            group=group,
            game_type_code="dominos",
            played_on=date(2026, 8, day),
            location=location,
            participants=participants,
        )

    _play(ca, 1)
    _play(ca, 2)
    _play(ny, 3)
    _play(blank, 4)

    result = query_player_play_locations(
        group,
        player_id=nancy.pk,
        game_type_code="dominos",
        group_by="state",
    )

    assert result["total_games"] == 4
    assert result["games_unknown_region"] == 1
    by_state = {row["state"]: row["games_played"] for row in result["rows"]}
    assert by_state["CA"] == 2
    assert by_state["NY"] == 1
    assert by_state[None] == 1
    assert "coverage_note" in result


@pytest.mark.django_db
def test_query_team_pairings_returns_observed_duo_teams(user, group):
    from leaderlodge.games.models import GameParticipantResult
    from leaderlodge.groups.services import add_guest_player
    from leaderlodge.groups.teams import resolve_side_player
    from leaderlodge.insights.tools.teams import query_team_pairings

    add_guest_player(group=group, display_name="Alex")
    players = list(group.players.order_by("pk"))
    team_ab = resolve_side_player(group=group, members=players[:2])
    team_cd = resolve_side_player(group=group, members=players[2:4])

    record_game(
        user=user,
        group=group,
        game_type_code="dominos",
        played_on="2026-01-20",
        participants=[
            ParticipantInput(
                player=team_ab,
                score=30,
                result=GameParticipantResult.Result.WIN,
                placement=0,
            ),
            ParticipantInput(
                player=team_cd,
                score=10,
                result=GameParticipantResult.Result.PLAYED,
                placement=1,
            ),
        ],
    )

    result = query_team_pairings(group, game_type_code="dominos")

    assert result["team_size"] == 2
    assert len(result["observed_duo_teams"]) == 2
    top = result["observed_duo_teams"][0]
    assert top["wins"] == 1
    assert len(top["member_labels"]) == 2
    assert "wins_display" in top
    assert "Do not recommend pairs that never played together" in result["guidance"]
