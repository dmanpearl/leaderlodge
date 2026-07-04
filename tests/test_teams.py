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
    resolve_side_player,
    team_display_name,
    team_member_players,
)
from leaderlodge.leaderboards.service import get_player_rankings


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
def test_resolve_side_player_solo_returns_person(group, user):
    owner, nancy, _, _ = _people(group)
    side = resolve_side_player(group=group, members=[nancy])
    assert side.pk == nancy.pk
    assert side.is_team is False


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
def test_team_vesting_uses_lowest_member_games_played(group, user):
    from leaderlodge.leaderboards.ranking import (
        apply_vesting_to_rank_score,
        compute_rank_score,
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
    # Nancy has 21 games, Zach has 2; vesting uses min = 2, not team games = 1.
    expected = apply_vesting_to_rank_score(
        compute_rank_score(
            points_total=team_row.finish_points,
            games_played=team_row.games_played,
        ),
        2.0,
    )
    assert team_row.rank_score == pytest.approx(expected)
    not_team_only = apply_vesting_to_rank_score(
        compute_rank_score(
            points_total=team_row.finish_points,
            games_played=team_row.games_played,
        ),
        1.0,
    )
    assert team_row.rank_score != pytest.approx(not_team_only)
