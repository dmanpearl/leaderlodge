from datetime import date

import pytest
from django.contrib.auth.models import User
from django.test import override_settings

from leaderlodge.games.scoring import assign_results_from_scores
from leaderlodge.games.services import ParticipantInput, record_game
from leaderlodge.groups.services import add_guest_player, create_group_with_owner
from leaderlodge.leaderboards.ranking import (
    TIE_WIN_POINTS_FACTOR,
    apply_vesting_to_rank_score,
    compute_finish_points,
    compute_rank_score,
    compute_vesting_multiplier,
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


@override_settings(LEADERBOARD_VESTING_COUNT=20, LEADERBOARD_VESTING_FACTOR=0.5)
def test_compute_vesting_multiplier():
    assert compute_vesting_multiplier(0) == 0.0
    assert compute_vesting_multiplier(20) == 1.0
    assert compute_vesting_multiplier(21) == 1.0
    assert compute_vesting_multiplier(10) == pytest.approx(0.75)
    assert compute_vesting_multiplier(1) == pytest.approx(0.525)


@override_settings(LEADERBOARD_VESTING_COUNT=20, LEADERBOARD_VESTING_FACTOR=0.5)
def test_apply_vesting_to_rank_score():
    assert apply_vesting_to_rank_score(2.0, 20) == pytest.approx(2.0)
    assert apply_vesting_to_rank_score(2.0, 10) == pytest.approx(1.5)


def test_compute_rank_score():
    assert compute_rank_score(points_total=8, games_played=3) == pytest.approx(8 / 3)
    assert compute_rank_score(points_total=0, games_played=0) == 0.0


def _record_progressive(user, group, players, winner):
    rows = [{"player": player, "score": index * 10} for index, player in enumerate(players, start=1)]
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
    assert by_player[alice.pk].rank_score > by_player[bob.pk].rank_score
    assert by_player[alice.pk].rank == 1


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
    assert alice_row.finish_points == pytest.approx(2.667, abs=0.01)
    assert alice_row.rank_score > 0


@pytest.mark.django_db
def test_tie_contributes_half_finish_points(user, group):
    players = list(group.players.order_by("pk"))[:2]
    rows = [
        {"player": players[0], "score": 20},
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

    rankings = get_player_rankings(group, game_type_code="dominos")
    for row in rankings:
        expected_win_points = 2 * TIE_WIN_POINTS_FACTOR
        expected_finish_points = compute_finish_points(
            player_count=2,
            placement=0,
            is_tie=True,
        )
        assert row.win_points == pytest.approx(expected_win_points)
        assert row.finish_points == pytest.approx(expected_finish_points)
        assert row.rank_score == pytest.approx(
            apply_vesting_to_rank_score(1.0, row.games_played)
        )


@pytest.mark.django_db
@override_settings(LEADERBOARD_VESTING_COUNT=20, LEADERBOARD_VESTING_FACTOR=0.5)
def test_vesting_penalizes_one_game_wonders(user, group):
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
        apply_vesting_to_rank_score(raw_score, winner.games_played)
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

    vested_rankings = get_player_rankings(group, game_type_code="dominos")
    vested_winner = next(row for row in vested_rankings if row.wins > 0)
    assert vested_winner.games_played == pytest.approx(20)
    assert vested_winner.rank_score == pytest.approx(2.0)
    assert vested_winner.rank_score > winner.rank_score


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
        detail.raw_rank_score * detail.vesting_multiplier
    )

    labels = [row.label for row in detail.placements]
    assert "1st" in labels
    assert "2nd" in labels
    first = next(row for row in detail.placements if row.label == "1st")
    second = next(row for row in detail.placements if row.label == "2nd")
    assert first.weighted_count == pytest.approx(1)
    assert second.weighted_count == pytest.approx(1)
    assert first.field_sizes[0].player_count == 3
    assert second.field_sizes[0].player_count == 4
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
