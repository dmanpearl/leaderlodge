import pytest
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone

from leaderlodge.games.models import GameParticipantResult
from leaderlodge.games.services import ParticipantInput, record_game
from leaderlodge.groups.services import add_guest_player, create_group_with_owner
from leaderlodge.groups.teams import (
    MAX_TEAM_SIZE,
    game_list_column_label_lines,
    resolve_side_player,
    team_display_name,
    team_member_players,
)
from leaderlodge.leaderboards.service import get_player_rank_detail, get_player_rankings


@pytest.fixture
def user(db):
    return User.objects.create_user(username="david", password="test-pass-123")


@pytest.fixture
def group(user):
    return create_group_with_owner(user=user, name="Dom Club")


def _people(group):
    owner = group.players.filter(linked_user__isnull=False).first()
    nancy = add_guest_player(group=group, display_name="Nancy")
    zach = add_guest_player(group=group, display_name="Zach")
    izzy = add_guest_player(group=group, display_name="Izzy")
    return owner, nancy, zach, izzy


@pytest.mark.django_db
def test_game_list_column_label_lines_splits_team_names(group, user):
    _, nancy, zach, _ = _people(group)
    team = resolve_side_player(group=group, members=[nancy, zach])
    assert game_list_column_label_lines(team) == ["Nancy", "Zach"]
    assert game_list_column_label_lines(nancy) == ["Nancy"]


@pytest.mark.django_db
def test_resolve_side_player_creates_team_with_sorted_label(group, user):
    _, nancy, zach, _ = _people(group)
    team = resolve_side_player(group=group, members=[zach, nancy])
    assert team.is_team is True
    assert team.display_name == "Nancy+Zach"
    assert team_display_name([zach, nancy]) == "Nancy+Zach"
    members = team_member_players(team)
    assert [m.display_label for m in members] == ["Nancy", "Zach"]


@pytest.mark.django_db
def test_resolve_side_player_reuses_team_when_member_pks_differ_from_label_order(
    group,
    user,
):
    """Member match must ignore label sort order vs player pk order."""
    _, nancy, zach, _ = _people(group)
    if nancy.pk < zach.pk:
        nancy, zach = zach, nancy

    team_a = resolve_side_player(group=group, members=[nancy, zach])
    team_b = resolve_side_player(group=group, members=[zach, nancy])
    assert team_b.pk == team_a.pk


@pytest.mark.django_db
def test_resolve_side_player_reuses_team_and_refreshes_label(group, user):
    _, nancy, zach, _ = _people(group)
    team_a = resolve_side_player(group=group, members=[nancy, zach])
    team_a.display_name = "Stale"
    team_a.save(update_fields=["display_name"])
    team_b = resolve_side_player(group=group, members=[zach, nancy])
    assert team_b.pk == team_a.pk
    assert team_b.display_name == "Nancy+Zach"


@pytest.mark.django_db
def test_record_team_game_credits_members_and_team(group, user):
    owner, nancy, zach, izzy = _people(group)
    team_nz = resolve_side_player(group=group, members=[nancy, zach])
    team_di = resolve_side_player(group=group, members=[owner, izzy])

    record_game(
        user=user,
        group=group,
        game_type_code="dominos",
        played_on=timezone.localdate(),
        participants=[
            ParticipantInput(
                player=team_nz,
                score=30,
                result=GameParticipantResult.Result.WIN,
                placement=0,
            ),
            ParticipantInput(
                player=team_di,
                score=10,
                result=GameParticipantResult.Result.PLAYED,
                placement=1,
            ),
        ],
    )

    rankings = get_player_rankings(group, game_type_code="dominos")
    by_label = {row.player.display_label: row for row in rankings}
    assert by_label["Nancy"].wins == 1
    assert by_label["Zach"].wins == 1
    assert by_label["Nancy+Zach"].wins == 1
    other_team_label = team_display_name([owner, izzy])
    assert by_label[owner.display_label].games_played == 1
    assert by_label["Izzy"].games_played == 1
    assert by_label[other_team_label].games_played == 1
    assert by_label[owner.display_label].wins == 0

    team_only = get_player_rankings(group, game_type_code="dominos", player_type="team")
    assert {row.player.display_label for row in team_only} == {
        "Nancy+Zach",
        other_team_label,
    }


@pytest.mark.django_db
def test_record_game_rejects_shared_person_across_sides(group, user):
    _, nancy, zach, izzy = _people(group)
    team_a = resolve_side_player(group=group, members=[nancy, zach])
    team_b = resolve_side_player(group=group, members=[nancy, izzy])
    with pytest.raises(ValidationError, match="more than one side"):
        record_game(
            user=user,
            group=group,
            game_type_code="dominos",
            played_on=timezone.localdate(),
            participants=[
                ParticipantInput(
                    player=team_a,
                    score=30,
                    result=GameParticipantResult.Result.WIN,
                    placement=0,
                ),
                ParticipantInput(
                    player=team_b,
                    score=10,
                    result=GameParticipantResult.Result.PLAYED,
                    placement=1,
                ),
            ],
        )


@pytest.mark.django_db
def test_record_team_game_via_form(client, user, group):
    owner, nancy, zach, izzy = _people(group)
    client.force_login(user)
    response = client.post(
        reverse("games:create"),
        {
            "action": "save",
            "group": str(group.pk),
            "game_type_code": "dominos",
            "played_on": timezone.localdate().isoformat(),
            "participant_player_id": [str(nancy.pk), str(owner.pk)],
            "participant_guest_name": ["", ""],
            "participant_teammate_player_id": [str(zach.pk), str(izzy.pk)],
            "participant_teammate_guest_name": ["", ""],
            "participant_score": ["30", "10"],
        },
    )
    assert response.status_code == 302
    rankings = get_player_rankings(group, game_type_code="dominos")
    by_label = {row.player.display_label: row for row in rankings}
    assert by_label["Nancy"].wins == 1
    assert by_label["Zach"].wins == 1
    assert by_label["Nancy+Zach"].wins == 1


@pytest.mark.django_db
def test_max_team_size_is_two(group, user):
    _, nancy, zach, izzy = _people(group)
    assert MAX_TEAM_SIZE == 2
    with pytest.raises(ValidationError, match="at most 2"):
        resolve_side_player(group=group, members=[nancy, zach, izzy])


@pytest.mark.django_db
def test_player_type_people_excludes_teams(group, user):
    from leaderlodge.groups.teams import matches_player_type

    owner, nancy, zach, _ = _people(group)
    team = resolve_side_player(group=group, members=[nancy, zach])
    assert matches_player_type(owner, "people") is True
    assert matches_player_type(nancy, "people") is True
    assert matches_player_type(team, "people") is False
    assert matches_player_type(team, "team") is True

    record_game(
        user=user,
        group=group,
        game_type_code="dominos",
        played_on=timezone.localdate(),
        participants=[
            ParticipantInput(
                player=team,
                score=30,
                result=GameParticipantResult.Result.WIN,
                placement=0,
            ),
            ParticipantInput(
                player=owner,
                score=10,
                result=GameParticipantResult.Result.PLAYED,
                placement=1,
            ),
        ],
    )
    people = get_player_rankings(group, game_type_code="dominos", player_type="people")
    assert all(not row.player.is_team for row in people)
    assert {row.player.display_label for row in people} >= {
        "Nancy",
        "Zach",
        owner.display_label,
    }


@pytest.mark.django_db
def test_team_bayesian_uses_team_games_played(group, user):
    from leaderlodge.leaderboards.ranking import (
        compute_rank_score,
        compute_team_bayesian_factor,
    )

    owner, nancy, zach, _ = _people(group)
    for _ in range(20):
        record_game(
            user=user,
            group=group,
            game_type_code="dominos",
            played_on=timezone.localdate(),
            participants=[
                ParticipantInput(
                    player=nancy,
                    score=30,
                    result=GameParticipantResult.Result.WIN,
                    placement=0,
                ),
                ParticipantInput(
                    player=owner,
                    score=10,
                    result=GameParticipantResult.Result.PLAYED,
                    placement=1,
                ),
            ],
        )
    record_game(
        user=user,
        group=group,
        game_type_code="dominos",
        played_on=timezone.localdate(),
        participants=[
            ParticipantInput(
                player=zach,
                score=30,
                result=GameParticipantResult.Result.WIN,
                placement=0,
            ),
            ParticipantInput(
                player=owner,
                score=10,
                result=GameParticipantResult.Result.PLAYED,
                placement=1,
            ),
        ],
    )
    team = resolve_side_player(group=group, members=[nancy, zach])
    record_game(
        user=user,
        group=group,
        game_type_code="dominos",
        played_on=timezone.localdate(),
        participants=[
            ParticipantInput(
                player=team,
                score=30,
                result=GameParticipantResult.Result.WIN,
                placement=0,
            ),
            ParticipantInput(
                player=owner,
                score=10,
                result=GameParticipantResult.Result.PLAYED,
                placement=1,
            ),
        ],
    )

    rankings = get_player_rankings(group, game_type_code="dominos", player_type="team")
    team_row = rankings[0]
    assert team_row.player.pk == team.pk
    assert team_row.games_played == 1.0
    # Team row Bayesian uses team games (1), not member career totals (21 and 2).
    raw_rank_score = compute_rank_score(
        points_total=team_row.finish_points,
        games_played=team_row.games_played,
    )
    expected = raw_rank_score * compute_team_bayesian_factor(team_row.games_played)
    assert team_row.rank_score == pytest.approx(expected)
    member_average = raw_rank_score * compute_team_bayesian_factor(11.5)
    assert team_row.rank_score != pytest.approx(member_average)


@pytest.mark.django_db
def test_team_with_more_games_ranks_above_same_raw_one_game_team(group, user):
    from leaderlodge.games.scoring import assign_results_from_scores
    from leaderlodge.games.services import ParticipantInput, record_game
    from leaderlodge.leaderboards.ranking import compute_rank_score

    owner, nancy, zach, _ = _people(group)
    team_once = resolve_side_player(group=group, members=[nancy, zach])
    for _ in range(3):
        record_game(
            user=user,
            group=group,
            game_type_code="dominos",
            played_on=timezone.localdate(),
            participants=[
                ParticipantInput(
                    player=team_once,
                    score=30,
                    result=GameParticipantResult.Result.WIN,
                    placement=0,
                ),
                ParticipantInput(
                    player=owner,
                    score=10,
                    result=GameParticipantResult.Result.PLAYED,
                    placement=1,
                ),
            ],
        )

    team_one = resolve_side_player(group=group, members=[owner, nancy])
    rows = [
        {"player": team_one, "score": 30},
        {"player": zach, "score": 10},
    ]
    assign_results_from_scores(rows, "dominos")
    record_game(
        user=user,
        group=group,
        game_type_code="dominos",
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

    rankings = get_player_rankings(group, game_type_code="dominos", player_type="team")
    by_team = {row.player.display_label: row for row in rankings}
    raw_once = compute_rank_score(
        points_total=by_team[team_once.display_label].finish_points,
        games_played=by_team[team_once.display_label].games_played,
    )
    raw_one = compute_rank_score(
        points_total=by_team[team_one.display_label].finish_points,
        games_played=by_team[team_one.display_label].games_played,
    )
    assert raw_once == pytest.approx(raw_one)
    assert (
        by_team[team_once.display_label].rank_score
        > by_team[team_one.display_label].rank_score
    )


@pytest.mark.django_db
def test_rookie_gets_reduced_individual_credit_from_team_win(group, user):
    from leaderlodge.leaderboards.ranking import (
        compute_bayesian_factor,
        team_member_finish_credit,
    )

    owner, nancy, zach, _ = _people(group)
    for _ in range(20):
        record_game(
            user=user,
            group=group,
            game_type_code="dominos",
            played_on=timezone.localdate(),
            participants=[
                ParticipantInput(
                    player=nancy,
                    score=30,
                    result=GameParticipantResult.Result.WIN,
                    placement=0,
                ),
                ParticipantInput(
                    player=owner,
                    score=10,
                    result=GameParticipantResult.Result.PLAYED,
                    placement=1,
                ),
            ],
        )

    team = resolve_side_player(group=group, members=[nancy, zach])
    record_game(
        user=user,
        group=group,
        game_type_code="dominos",
        played_on=timezone.localdate(),
        participants=[
            ParticipantInput(
                player=team,
                score=30,
                result=GameParticipantResult.Result.WIN,
                placement=0,
            ),
            ParticipantInput(
                player=owner,
                score=10,
                result=GameParticipantResult.Result.PLAYED,
                placement=1,
            ),
        ],
    )

    rankings = get_player_rankings(
        group, game_type_code="dominos", player_type="people"
    )
    by_label = {row.player.display_label: row for row in rankings}
    nancy_row = by_label["Nancy"]
    zach_row = by_label["Zach"]

    team_rankings = get_player_rankings(
        group, game_type_code="dominos", player_type="team"
    )
    team_row = next(
        row for row in team_rankings if row.player.display_label == "Nancy+Zach"
    )

    side_finish_points = 60.0
    assert team_row.finish_points == pytest.approx(side_finish_points)
    assert nancy_row.finish_points > zach_row.finish_points
    assert zach_row.finish_points == pytest.approx(
        team_member_finish_credit(
            side_finish_points,
            member_games_played=1.0,
            apply_experience_weight=True,
        )
    )
    assert nancy_row.finish_points > side_finish_points * compute_bayesian_factor(1.0)
    assert zach_row.rank_score < nancy_row.rank_score


@pytest.mark.django_db
def test_rank_detail_partner_breakdown_shows_record_per_teammate(group, user):
    from leaderlodge.leaderboards.ranking import (
        ordinal_place_label,
        partner_rank_pill_class,
    )

    owner, nancy, zach, _ = _people(group)
    opponent = add_guest_player(group=group, display_name="Opponent")

    def _play(team_side, *, wins, losses):
        for _ in range(wins):
            record_game(
                user=user,
                group=group,
                game_type_code="dominos",
                played_on=timezone.localdate(),
                participants=[
                    ParticipantInput(
                        player=team_side,
                        score=30,
                        result=GameParticipantResult.Result.WIN,
                        placement=0,
                    ),
                    ParticipantInput(
                        player=opponent,
                        score=10,
                        result=GameParticipantResult.Result.PLAYED,
                        placement=1,
                    ),
                ],
            )
        for _ in range(losses):
            record_game(
                user=user,
                group=group,
                game_type_code="dominos",
                played_on=timezone.localdate(),
                participants=[
                    ParticipantInput(
                        player=opponent,
                        score=30,
                        result=GameParticipantResult.Result.WIN,
                        placement=0,
                    ),
                    ParticipantInput(
                        player=team_side,
                        score=10,
                        result=GameParticipantResult.Result.PLAYED,
                        placement=1,
                    ),
                ],
            )

    team_with_nancy = resolve_side_player(group=group, members=[owner, nancy])
    team_with_zach = resolve_side_player(group=group, members=[owner, zach])
    _play(team_with_nancy, wins=3, losses=0)
    _play(team_with_zach, wins=0, losses=1)

    detail = get_player_rank_detail(group, owner, game_type_code="dominos")

    assert detail is not None
    by_partner = {row.partner_label: row for row in detail.partner_breakdown}
    assert set(by_partner) == {"Nancy", "Zach"}
    assert by_partner["Nancy"].games_played == pytest.approx(3.0)
    assert by_partner["Nancy"].wins == pytest.approx(3.0)
    assert by_partner["Nancy"].win_pct == pytest.approx(100.0)
    assert by_partner["Zach"].games_played == pytest.approx(1.0)
    assert by_partner["Zach"].wins == pytest.approx(0.0)
    assert by_partner["Zach"].win_pct == pytest.approx(0.0)
    # Sorted by partner rank first; Nancy's undefeated record with the owner
    # gives her a better individual rank than Zach's 0-1 record.
    assert detail.partner_breakdown[0].partner_label == "Nancy"

    all_rankings = get_player_rankings(group, game_type_code="dominos")
    rank_by_label = {row.player.display_label: row.rank for row in all_rankings}
    assert by_partner["Nancy"].partner_rank_label == ordinal_place_label(
        rank_by_label["Nancy"] - 1
    )
    assert by_partner["Zach"].partner_rank_label == ordinal_place_label(
        rank_by_label["Zach"] - 1
    )
    assert by_partner["Nancy"].partner_rank == rank_by_label["Nancy"]
    assert by_partner["Zach"].partner_rank == rank_by_label["Zach"]
    assert by_partner["Nancy"].partner_rank_pill_class == partner_rank_pill_class(
        rank_by_label["Nancy"]
    )


@pytest.mark.django_db
def test_rank_detail_partner_breakdown_rank_beats_pairing_win_pct(group, user):
    """Partner order follows each partner's own leaderboard rank, not how well
    they did specifically when paired with the viewed player."""
    owner, nancy, zach, izzy = _people(group)
    opponent = add_guest_player(group=group, display_name="Opponent")

    def _play(winner, loser):
        record_game(
            user=user,
            group=group,
            game_type_code="dominos",
            played_on=timezone.localdate(),
            participants=[
                ParticipantInput(
                    player=winner,
                    score=30,
                    result=GameParticipantResult.Result.WIN,
                    placement=0,
                ),
                ParticipantInput(
                    player=loser,
                    score=10,
                    result=GameParticipantResult.Result.PLAYED,
                    placement=1,
                ),
            ],
        )

    team_with_nancy = resolve_side_player(group=group, members=[owner, nancy])
    team_with_zach = resolve_side_player(group=group, members=[owner, zach])
    # Paired with the owner, Nancy wins every game and Zach loses every game.
    for _ in range(3):
        _play(team_with_nancy, opponent)
    _play(opponent, team_with_zach)
    # Outside of that pairing, Zach racks up solo wins against Izzy, giving
    # him a much better overall rank than Nancy's team-only record.
    for _ in range(10):
        _play(zach, izzy)

    detail = get_player_rank_detail(group, owner, game_type_code="dominos")
    all_rankings = get_player_rankings(group, game_type_code="dominos")
    rank_by_label = {row.player.display_label: row.rank for row in all_rankings}

    assert detail is not None
    by_partner = {row.partner_label: row for row in detail.partner_breakdown}
    # Nancy has the better win percentage when paired with the owner...
    assert by_partner["Nancy"].win_pct == pytest.approx(100.0)
    assert by_partner["Zach"].win_pct == pytest.approx(0.0)
    # ...but Zach has the better overall rank thanks to his outside wins...
    assert rank_by_label["Zach"] < rank_by_label["Nancy"]
    # ...so Zach is listed first, ranked ahead of Nancy despite the 0-1 record.
    assert [row.partner_label for row in detail.partner_breakdown] == [
        "Zach",
        "Nancy",
    ]


def test_partner_breakdown_sort_key_puts_unranked_partners_last():
    """Unit test for the sort key itself: an unranked partner (no single
    resolvable rank, e.g. a defensive edge case outside normal 2-player teams)
    sorts after every ranked partner regardless of win percentage."""
    from leaderlodge.leaderboards.service import (
        PartnerBreakdown,
        _partner_breakdown_sort_key,
    )

    ranked_low = PartnerBreakdown(
        partner_label="Alice",
        partner_rank=5,
        partner_rank_label="4th",
        partner_rank_pill_class="",
        games_played=10.0,
        wins=10.0,
        win_pct=100.0,
        finish_points=0.0,
        avg_finish_points=0.0,
    )
    unranked_high_win_pct = PartnerBreakdown(
        partner_label="Bob",
        partner_rank=None,
        partner_rank_label="",
        partner_rank_pill_class="",
        games_played=10.0,
        wins=10.0,
        win_pct=100.0,
        finish_points=0.0,
        avg_finish_points=0.0,
    )
    ranked_high = PartnerBreakdown(
        partner_label="Carol",
        partner_rank=1,
        partner_rank_label="1st",
        partner_rank_pill_class="",
        games_played=1.0,
        wins=0.0,
        win_pct=0.0,
        finish_points=0.0,
        avg_finish_points=0.0,
    )

    ordered = sorted(
        [ranked_low, unranked_high_win_pct, ranked_high],
        key=_partner_breakdown_sort_key,
    )
    assert [row.partner_label for row in ordered] == ["Carol", "Alice", "Bob"]
