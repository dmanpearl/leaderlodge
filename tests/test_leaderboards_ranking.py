from datetime import date

import pytest
from django.contrib.auth.models import User

from leaderlodge.games.models import GameParticipantResult
from leaderlodge.games.scoring import assign_results_from_scores
from leaderlodge.games.services import ParticipantInput, record_game
from leaderlodge.groups.services import add_guest_player, create_group_with_owner
from leaderlodge.leaderboards.ranking import (
    TIE_WIN_POINTS_FACTOR,
    apply_vesting_to_rank_score,
    compute_rank_score,
    compute_vesting_multiplier,
)
from leaderlodge.leaderboards.service import get_player_rankings


@pytest.fixture
def user(db):
    return User.objects.create_user(username="david", password="test-pass-123")


@pytest.fixture
def group(user):
    group = create_group_with_owner(user=user, name="Dom Club")
    add_guest_player(group=group, display_name="Pat")
    return group


def test_compute_vesting_multiplier():
    assert compute_vesting_multiplier(0) == 0.0
    assert compute_vesting_multiplier(20) == 1.0
    assert compute_vesting_multiplier(21) == 1.0
    assert compute_vesting_multiplier(10) == pytest.approx(0.75)
    assert compute_vesting_multiplier(1) == pytest.approx(0.525)


def test_apply_vesting_to_rank_score():
    assert apply_vesting_to_rank_score(2.0, 20) == pytest.approx(2.0)
    assert apply_vesting_to_rank_score(2.0, 10) == pytest.approx(1.5)


def test_compute_rank_score():
    assert compute_rank_score(win_points=8, games_played=3) == pytest.approx(8 / 3)
    assert compute_rank_score(win_points=0, games_played=0) == 0.0


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
    assert by_player[alice.pk].rank_score > by_player[bob.pk].rank_score
    assert by_player[alice.pk].rank == 1


@pytest.mark.django_db
def test_tie_contributes_half_win_points(user, group):
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
        expected = 2 * TIE_WIN_POINTS_FACTOR
        assert row.win_points == pytest.approx(expected)
        assert row.rank_score == pytest.approx(
            apply_vesting_to_rank_score(1.0, row.games_played)
        )


@pytest.mark.django_db
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
        win_points=winner.win_points,
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
