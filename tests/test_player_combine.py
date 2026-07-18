import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone

from leaderlodge.games.models import GameParticipantResult
from leaderlodge.games.services import ParticipantInput, record_game
from leaderlodge.groups.invites import create_email_invite_for_guest
from leaderlodge.groups.models import GroupPlayer
from leaderlodge.groups.player_combine import combine_players
from leaderlodge.groups.services import (
    add_guest_player,
    add_group_member,
    create_group_with_owner,
)


@pytest.fixture
def owner(db):
    return User.objects.create_user(username="owner", password="test-pass-123")


@pytest.fixture
def editor(db):
    return User.objects.create_user(username="editor", password="test-pass-123")


@pytest.fixture
def staff_user(db):
    return User.objects.create_user(
        username="staff",
        password="test-pass-123",
        is_staff=True,
    )


@pytest.fixture
def group(owner, editor):
    from leaderlodge.groups.models import GroupMembership

    group = create_group_with_owner(user=owner, name="Game Night")
    add_group_member(group=group, user=editor, role=GroupMembership.Role.EDITOR)
    return group


def _guest(group, name):
    return add_guest_player(group=group, display_name=name)


@pytest.mark.django_db
def test_combine_guests_merges_game_results(owner, group):
    pat = _guest(group, "Pat")
    patty = _guest(group, "Patty")
    players = list(group.players.order_by("pk"))
    record_game(
        user=owner,
        group=group,
        game_type_code="dominos",
        played_on=timezone.localdate(),
        participants=[
            ParticipantInput(
                player=players[0],
                score=30,
                result=GameParticipantResult.Result.WIN,
                placement=0,
            ),
            ParticipantInput(
                player=pat,
                score=20,
                result=GameParticipantResult.Result.PLAYED,
                placement=1,
            ),
        ],
    )
    record_game(
        user=owner,
        group=group,
        game_type_code="dominos",
        played_on=timezone.localdate(),
        participants=[
            ParticipantInput(
                player=players[0],
                score=25,
                result=GameParticipantResult.Result.WIN,
                placement=0,
            ),
            ParticipantInput(
                player=patty,
                score=15,
                result=GameParticipantResult.Result.PLAYED,
                placement=1,
            ),
        ],
    )

    combine_players(keeper=pat, source=patty)

    assert not GroupPlayer.objects.filter(pk=patty.pk).exists()
    assert pat.game_results.count() == 2


@pytest.mark.django_db
def test_combine_fails_when_players_shared_a_game(owner, group):
    pat = _guest(group, "Pat")
    patty = _guest(group, "Patty")
    players = list(group.players.order_by("pk"))
    record_game(
        user=owner,
        group=group,
        game_type_code="dominos",
        played_on=timezone.localdate(),
        participants=[
            ParticipantInput(
                player=players[0],
                score=30,
                result=GameParticipantResult.Result.WIN,
                placement=0,
            ),
            ParticipantInput(
                player=pat,
                score=20,
                result=GameParticipantResult.Result.PLAYED,
                placement=1,
            ),
            ParticipantInput(
                player=patty,
                score=10,
                result=GameParticipantResult.Result.PLAYED,
                placement=2,
            ),
        ],
    )

    with pytest.raises(ValueError, match="played in the same game"):
        combine_players(keeper=pat, source=patty)


@pytest.mark.django_db
def test_combine_guest_into_linked_user_transfers_account(owner, group):
    guest = _guest(group, "Pat")
    linked = group.players.get(linked_user=owner)

    combine_players(keeper=linked, source=guest)

    assert not GroupPlayer.objects.filter(pk=guest.pk).exists()
    linked.refresh_from_db()
    assert linked.linked_user_id == owner.pk


@pytest.mark.django_db
def test_combine_fails_when_both_have_linked_users(group, owner, editor):
    linked_owner = group.players.get(linked_user=owner)
    linked_editor = group.players.get(linked_user=editor)

    with pytest.raises(ValueError, match="linked account"):
        combine_players(keeper=linked_owner, source=linked_editor)


@pytest.mark.django_db
def test_combine_moves_pending_invite(owner, group):
    guest = _guest(group, "Pat")
    keeper = _guest(group, "Patty")
    invite = create_email_invite_for_guest(
        group=group,
        guest_player=guest,
        email="friend@example.com",
        invited_by=owner,
    )

    combine_players(keeper=keeper, source=guest)

    invite.refresh_from_db()
    assert invite.guest_player_id == keeper.pk


@pytest.mark.django_db
def test_editor_cannot_open_combine_page(client, editor, group):
    keeper = _guest(group, "Pat")
    client.force_login(editor)
    response = client.get(
        reverse(
            "groups:player_combine", kwargs={"pk": group.pk, "player_pk": keeper.pk}
        )
    )
    assert response.status_code == 404


@pytest.mark.django_db
def test_staff_member_can_combine_players(client, staff_user, group):
    add_group_member(group=group, user=staff_user)
    pat = _guest(group, "Pat")
    patty = _guest(group, "Patty")
    client.force_login(staff_user)

    response = client.post(
        reverse("groups:player_combine", kwargs={"pk": group.pk, "player_pk": pat.pk}),
        {"source": str(patty.pk)},
    )
    assert response.status_code == 200
    assert "Confirm player merge" in response.content.decode()

    response = client.post(
        reverse("groups:player_combine", kwargs={"pk": group.pk, "player_pk": pat.pk}),
        {"source": str(patty.pk), "confirm": "yes"},
    )
    assert response.status_code == 302
    assert not GroupPlayer.objects.filter(pk=patty.pk).exists()
    assert GroupPlayer.objects.filter(pk=pat.pk).exists()


