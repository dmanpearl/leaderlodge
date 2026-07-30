from datetime import date

import pytest
from django.contrib.auth.models import User
from django.test import override_settings

from leaderlodge.games.scoring import assign_results_from_scores
from leaderlodge.games.services import ParticipantInput, record_game
from leaderlodge.groups.services import add_guest_player, create_group_with_owner
from leaderlodge.leaderboards.ranking import (
    FINISH_POINTS_EXPONENT,
    LOW_WINS_REFERENCE_SCORE,
    TIE_WIN_POINTS_FACTOR,
    FinishPointsCredit,
    apply_bayesian_to_rank_score,
    compute_bayesian_factor,
    compute_display_rank_score,
    compute_finish_points,
    compute_rank_score,
    compute_score_magnitude,
    rank_score_magnitude_for_result,
    team_member_finish_credit,
)
from leaderlodge.leaderboards.service import get_player_rank_detail, get_player_rankings


@pytest.fixture
def user(db):
    return User.objects.create_user(username="david", password="test-pass-123")


@pytest.fixture
def group(user):
    group = create_group_with_owner(user=user, name="Dom Club")
    add_guest_player(group=group, display_name="Pat")
    return group


def test_compute_score_magnitude_low_wins():
    assert compute_score_magnitude(
        20, [20, 35, 215, 480], low_wins=True, placement=0
    ) == pytest.approx(LOW_WINS_REFERENCE_SCORE - 20)
    assert compute_score_magnitude(
        35, [20, 35, 215, 480], low_wins=True, placement=1
    ) == pytest.approx(480 - 35)
    assert compute_score_magnitude(
        215, [20, 35, 215, 480], low_wins=True, placement=2
    ) == pytest.approx(480 - 215)
    assert compute_score_magnitude(
        35, [20, 35, 215, 480], low_wins=True, placement=1
    ) > compute_score_magnitude(215, [20, 35, 215, 480], low_wins=True, placement=2)


def test_rank_score_magnitude_pickleball_uses_unity():
    assert rank_score_magnitude_for_result(
        15,
        [15, 7],
        game_type_code="pickleball",
        placement=0,
    ) == pytest.approx(1.0)
    assert rank_score_magnitude_for_result(
        11,
        [11, 3],
        game_type_code="pickleball",
        placement=0,
    ) == pytest.approx(1.0)


def test_rank_score_magnitude_dominos_uses_recorded_score():
    assert rank_score_magnitude_for_result(
        30,
        [30, 10],
        game_type_code="dominos",
        placement=0,
    ) == pytest.approx(30.0)


def test_compute_finish_points():
    assert compute_finish_points(player_count=2, placement=0) == pytest.approx(2.0)
    assert compute_finish_points(player_count=2, placement=1) == pytest.approx(0.0)
    assert compute_finish_points(player_count=5, placement=0) == pytest.approx(5.0)
    assert compute_finish_points(player_count=5, placement=1) == pytest.approx(3.75)
    assert compute_finish_points(player_count=5, placement=4) == pytest.approx(0.0)
    assert compute_finish_points(player_count=3, placement=1) == pytest.approx(1.5)
    assert compute_finish_points(player_count=5, placement=1) > compute_finish_points(
        player_count=3, placement=1
    )
    assert compute_finish_points(
        player_count=2, placement=0, is_tie=True
    ) == pytest.approx(2.0 * TIE_WIN_POINTS_FACTOR)
    assert FINISH_POINTS_EXPONENT == 1.0


def test_mahjongg_wall_game_losers_earn_no_finish_points(user, group):
    players = [
        add_guest_player(group=group, display_name=f"Player {index}")
        for index in range(4)
    ]
    rows = [
        {"player": players[0], "score": 35},
        {"player": players[1], "score": 0},
        {"player": players[2], "score": 0},
        {"player": players[3], "score": 0},
    ]
    assign_results_from_scores(rows, "mahjongg")
    record_game(
        user=user,
        group=group,
        game_type_code="mahjongg",
        played_on=date(2026, 6, 20),
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

    rankings = get_player_rankings(group, game_type_code="mahjongg")
    by_player = {row.player.pk: row for row in rankings}

    assert by_player[players[0].pk].finish_points == pytest.approx(140.0)
    assert by_player[players[1].pk].finish_points == pytest.approx(0.0)
    assert by_player[players[2].pk].finish_points == pytest.approx(0.0)
    assert by_player[players[3].pk].finish_points == pytest.approx(0.0)


@override_settings(LEADERBOARD_BAYESIAN_K=20)
def test_apply_bayesian_to_rank_score():
    assert apply_bayesian_to_rank_score(2.0, 20) == pytest.approx(2.0 * (20 / 40))
    assert apply_bayesian_to_rank_score(2.0, 10) == pytest.approx(2.0 * (10 / 30))
    assert apply_bayesian_to_rank_score(4.0, 0.5) == pytest.approx(4.0 * (0.5 / 20.5))
    assert apply_bayesian_to_rank_score(4.0, 10, apply_bayesian=False) == pytest.approx(
        4.0
    )


@override_settings(LEADERBOARD_BAYESIAN_K=20)
def test_team_member_finish_credit_scales_by_member_games():
    side_points = 60.0
    rookie_credit = team_member_finish_credit(
        side_points,
        member_games_played=1.0,
        apply_experience_weight=True,
    )
    veteran_credit = team_member_finish_credit(
        side_points,
        member_games_played=20.0,
        apply_experience_weight=True,
    )
    assert rookie_credit == pytest.approx(side_points * compute_bayesian_factor(1.0))
    assert veteran_credit == pytest.approx(side_points * compute_bayesian_factor(20.0))
    assert veteran_credit > rookie_credit


@override_settings(LEADERBOARD_BAYESIAN_K=20)
def test_compute_display_rank_score_splits_solo_and_team_bayesian():
    credit = FinishPointsCredit(solo=100.0, team=10.0)
    score = compute_display_rank_score(
        credit=credit,
        games_played=10.0,
        player_is_team=False,
        effective_games_for_bayesian=10.0,
        apply_bayesian=True,
    )
    expected = (100.0 / 10.0) * compute_bayesian_factor(10.0) + (10.0 / 10.0)
    assert score == pytest.approx(expected)


def _record_progressive(user, group, players, winner):
    rows = [
        {"player": player, "score": index * 10}
        for index, player in enumerate(players, start=1)
    ]
    winner_row = next(row for row in rows if row["player"] == winner)
    winner_row["score"] = 0
    assign_results_from_scores(rows, "progressiverummy")
    record_game(
        user=user,
        group=group,
        game_type_code="progressiverummy",
        played_on=date(2026, 1, 1),
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


@pytest.mark.django_db
def test_rank_score_prefers_wins_in_larger_fields(user, group):
    alice = group.players.get(linked_user=user)
    bob = add_guest_player(group=group, display_name="Bob")
    carol = add_guest_player(group=group, display_name="Carol")
    dave = add_guest_player(group=group, display_name="Dave")
    eve = add_guest_player(group=group, display_name="Eve")

    _record_progressive(user, group, [alice, bob, carol], alice)
    _record_progressive(user, group, [alice, bob, carol, dave, eve], alice)
    _record_progressive(user, group, [alice, bob, carol, dave], bob)
    _record_progressive(user, group, [alice, bob, carol, dave, eve], carol)

    rankings = get_player_rankings(
        group,
        game_type_code="progressiverummy",
    )
    by_player = {row.player.pk: row for row in rankings}

    assert by_player[alice.pk].win_points == pytest.approx(8)
    assert by_player[bob.pk].win_points == pytest.approx(4)
    assert by_player[alice.pk].finish_points > by_player[bob.pk].finish_points
    assert all(by_player[alice.pk].win_points >= row.win_points for row in rankings)


@pytest.mark.django_db
def test_middle_placement_earns_finish_points(user, group):
    alice = group.players.get(linked_user=user)
    bob = add_guest_player(group=group, display_name="Bob")
    carol = add_guest_player(group=group, display_name="Carol")
    dave = add_guest_player(group=group, display_name="Dave")

    _record_progressive(user, group, [alice, bob, carol, dave], bob)

    rankings = get_player_rankings(
        group,
        game_type_code="progressiverummy",
    )
    alice_row = next(row for row in rankings if row.player.pk == alice.pk)

    assert alice_row.wins == 0
    assert alice_row.win_points == 0
    assert alice_row.finish_points == pytest.approx(80.0)
    assert alice_row.rank_score > 0


@pytest.mark.django_db
def test_tie_for_lead_uses_lower_place_and_earns_no_finish_points_in_two_player_game(
    user, group
):
    players = list(group.players.order_by("pk"))[:2]
    rows = [
        {"player": players[0], "score": 20},
        {"player": players[1], "score": 20},
    ]
    assign_results_from_scores(rows, "dominos")
    assert rows[0]["placement"] == 1
    assert rows[1]["placement"] == 1
    record_game(
        user=user,
        group=group,
        game_type_code="dominos",
        played_on=date(2026, 1, 1),
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

    rankings = get_player_rankings(group, game_type_code="dominos")
    for row in rankings:
        expected_win_points = 2 * TIE_WIN_POINTS_FACTOR
        assert row.win_points == pytest.approx(expected_win_points)
        assert row.finish_points == pytest.approx(0.0)


@pytest.mark.django_db
@override_settings(LEADERBOARD_BAYESIAN_K=20)
def test_bayesian_penalizes_one_game_wonders(user, group):
    players = list(group.players.order_by("pk"))[:2]
    rows = [
        {"player": players[0], "score": 30},
        {"player": players[1], "score": 20},
    ]
    assign_results_from_scores(rows, "dominos")
    record_game(
        user=user,
        group=group,
        game_type_code="dominos",
        played_on=date(2026, 1, 1),
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

    one_game_rankings = get_player_rankings(group, game_type_code="dominos")
    assert len(one_game_rankings) == 2

    winner = next(row for row in one_game_rankings if row.wins > 0)
    raw_score = compute_rank_score(
        points_total=winner.finish_points,
        games_played=winner.games_played,
    )
    assert winner.rank_score == pytest.approx(
        apply_bayesian_to_rank_score(raw_score, winner.games_played)
    )

    for _ in range(19):
        assign_results_from_scores(rows, "dominos")
        record_game(
            user=user,
            group=group,
            game_type_code="dominos",
            played_on=date(2026, 1, 2),
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

    more_games_rankings = get_player_rankings(group, game_type_code="dominos")
    more_games_winner = next(row for row in more_games_rankings if row.wins > 0)
    assert more_games_winner.games_played == pytest.approx(20)
    assert more_games_winner.rank_score == pytest.approx(60.0 * (20 / 40))
    assert more_games_winner.rank_score > winner.rank_score


@pytest.mark.django_db
def test_get_player_rank_detail_breakdown(user, group):
    alice = group.players.get(linked_user=user)
    bob = add_guest_player(group=group, display_name="Bob")
    carol = add_guest_player(group=group, display_name="Carol")
    dave = add_guest_player(group=group, display_name="Dave")

    _record_progressive(user, group, [alice, bob, carol], alice)
    _record_progressive(user, group, [alice, bob, carol, dave], bob)

    detail = get_player_rank_detail(
        group,
        alice,
        game_type_code="progressiverummy",
    )

    assert detail is not None
    assert detail.ranking.player.pk == alice.pk
    assert detail.ranking.finish_points > 0
    assert detail.raw_rank_score == pytest.approx(
        detail.ranking.finish_points / detail.ranking.games_played
    )
    assert detail.ranking.rank_score == pytest.approx(
        detail.raw_rank_score * detail.bayesian_factor
    )

    labels = [row.label for row in detail.placements]
    assert "1st" in labels
    assert "2nd" in labels
    first = next(row for row in detail.placements if row.label == "1st")
    second = next(row for row in detail.placements if row.label == "2nd")
    assert first.weighted_count == pytest.approx(1)
    assert second.weighted_count == pytest.approx(1)
    assert first.count_pct == pytest.approx(50.0)
    assert second.count_pct == pytest.approx(50.0)
    assert sum(row.count_pct for row in detail.placements) == pytest.approx(100.0)
    assert first.avg_finish_points == pytest.approx(
        first.finish_points / first.weighted_count
    )
    assert second.avg_finish_points == pytest.approx(
        second.finish_points / second.weighted_count
    )
    assert first.field_sizes[0].player_count == 3
    assert second.field_sizes[0].player_count == 4
    assert first.field_sizes[0].count_pct == pytest.approx(50.0)
    assert detail.supports_loser is True
    assert detail.loss_game_count >= 0
    assert detail.game_count == 2
    assert detail.first_game_date is not None
    assert detail.last_win_date is not None
    assert detail.first_win_date == detail.first_game_date
    assert detail.best_score is not None
    assert detail.worst_score is not None
    assert detail.score_low_wins is True
    assert detail.best_score.score <= detail.worst_score.score
    assert detail.podium_count > 0


@pytest.mark.django_db
@override_settings(LEADERBOARD_BAYESIAN_K=20)
def test_provisional_half_win_progressive_rummy_gets_penalized_rank_score(user, group):
    """Zach-style case: one half win should not rank near the top."""
    david = add_guest_player(group=group, display_name="David")
    nancy = add_guest_player(group=group, display_name="Nancy")
    sara = add_guest_player(group=group, display_name="Sara")
    zach = add_guest_player(group=group, display_name="Zach")
    jake = add_guest_player(group=group, display_name="Jake")

    rows = [
        {"player": david, "score": 215},
        {"player": nancy, "score": 35},
        {"player": sara, "score": 480},
        {"player": zach, "score": 20},
    ]
    assign_results_from_scores(rows, "progressiverummy")
    record_game(
        user=user,
        group=group,
        game_type_code="progressiverummy",
        played_on=date(2021, 4, 26),
        participants=[
            ParticipantInput(
                player=row["player"],
                score=row["score"],
                result=row["result"],
                placement=row["placement"],
            )
            for row in rows
        ],
        half_weight=2,
    )

    loss_rows = [
        {"player": jake, "score": 215},
        {"player": david, "score": 35},
        {"player": nancy, "score": 480},
        {"player": sara, "score": 20},
    ]
    assign_results_from_scores(loss_rows, "progressiverummy")
    record_game(
        user=user,
        group=group,
        game_type_code="progressiverummy",
        played_on=date(2021, 4, 27),
        participants=[
            ParticipantInput(
                player=row["player"],
                score=row["score"],
                result=row["result"],
                placement=row["placement"],
            )
            for row in loss_rows
        ],
    )

    veteran = add_guest_player(group=group, display_name="Veteran")
    for _ in range(3):
        _record_progressive(user, group, [david, nancy, sara, veteran], david)

    rankings = get_player_rankings(group, game_type_code="progressiverummy")
    by_player = {row.player.pk: row for row in rankings}
    zach_row = by_player[zach.pk]
    jake_row = by_player[jake.pk]
    david_row = by_player[david.pk]
    bayesian = compute_bayesian_factor(0.5)

    assert zach_row.games_played == pytest.approx(0.5)
    assert zach_row.wins == pytest.approx(0.5)
    assert zach_row.rank_score == pytest.approx(1920.0 * bayesian, abs=1.0)
    assert zach_row.rank_score > jake_row.rank_score
    assert zach_row.rank < jake_row.rank
    assert zach_row.rank > david_row.rank
