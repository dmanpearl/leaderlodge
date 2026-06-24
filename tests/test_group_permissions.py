import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from leaderlodge.groups.models import GroupMembership
from leaderlodge.groups.permissions import (
    can_remove_membership,
    can_set_membership_role,
    get_membership,
)
from leaderlodge.groups.services import add_group_member, create_group_with_owner


@pytest.fixture
def owner(db):
    return User.objects.create_user(username="owner", password="test-pass-123")


@pytest.fixture
def editor(db):
    return User.objects.create_user(username="editor", password="test-pass-123")


@pytest.fixture
def member(db):
    return User.objects.create_user(username="member", password="test-pass-123")


@pytest.fixture
def other_owner(db):
    return User.objects.create_user(username="coowner", password="test-pass-123")


@pytest.fixture
def group(owner, editor, member):
    group = create_group_with_owner(user=owner, name="Game Night")
    add_group_member(group=group, user=editor, role=GroupMembership.Role.EDITOR)
    add_group_member(group=group, user=member)
    return group


def _membership(group, user):
    return get_membership(user, group)


@pytest.mark.django_db
def test_plain_member_cannot_add_member(client, member, group, other_owner):
    client.force_login(member)
    response = client.post(
        reverse("groups:member_add", kwargs={"pk": group.pk}),
        {"user": other_owner.pk},
    )
    assert response.status_code == 404
    assert not GroupMembership.objects.filter(group=group, user=other_owner).exists()


@pytest.mark.django_db
def test_editor_can_add_member(client, editor, group, other_owner):
    client.force_login(editor)
    response = client.post(
        reverse("groups:member_add", kwargs={"pk": group.pk}),
        {"user": other_owner.pk},
    )
    assert response.status_code == 302
    assert GroupMembership.objects.filter(
        group=group,
        user=other_owner,
        role=GroupMembership.Role.MEMBER,
    ).exists()


@pytest.mark.django_db
def test_editor_cannot_remove_owner(client, editor, owner, group):
    owner_membership = _membership(group, owner)
    client.force_login(editor)
    response = client.post(
        reverse(
            "groups:member_remove",
            kwargs={"pk": group.pk, "membership_pk": owner_membership.pk},
        )
    )
    assert response.status_code == 302
    assert GroupMembership.objects.filter(pk=owner_membership.pk).exists()


@pytest.mark.django_db
def test_editor_cannot_demote_owner(client, editor, owner, group):
    owner_membership = _membership(group, owner)
    client.force_login(editor)
    response = client.post(
        reverse(
            "groups:member_update_role",
            kwargs={"pk": group.pk, "membership_pk": owner_membership.pk},
        ),
        {"role": GroupMembership.Role.EDITOR},
    )
    assert response.status_code == 302
    owner_membership.refresh_from_db()
    assert owner_membership.role == GroupMembership.Role.OWNER


@pytest.mark.django_db
def test_editor_can_remove_member(client, editor, member, group):
    member_membership = _membership(group, member)
    player = group.players.get(linked_user=member)
    client.force_login(editor)
    response = client.post(
        reverse(
            "groups:member_remove",
            kwargs={"pk": group.pk, "membership_pk": member_membership.pk},
        )
    )
    assert response.status_code == 302
    assert not GroupMembership.objects.filter(pk=member_membership.pk).exists()
    player.refresh_from_db()
    assert player.linked_user is None
    assert player.is_active is True


@pytest.mark.django_db
def test_editor_can_promote_member_to_editor(client, editor, member, group):
    member_membership = _membership(group, member)
    client.force_login(editor)
    response = client.post(
        reverse(
            "groups:member_update_role",
            kwargs={"pk": group.pk, "membership_pk": member_membership.pk},
        ),
        {"role": GroupMembership.Role.EDITOR},
    )
    assert response.status_code == 302
    member_membership.refresh_from_db()
    assert member_membership.role == GroupMembership.Role.EDITOR


@pytest.mark.django_db
def test_editor_cannot_promote_member_to_owner(client, editor, member, group):
    member_membership = _membership(group, member)
    actor = _membership(group, editor)
    assert not can_set_membership_role(
        actor, member_membership, GroupMembership.Role.OWNER
    )
    client.force_login(editor)
    response = client.post(
        reverse(
            "groups:member_update_role",
            kwargs={"pk": group.pk, "membership_pk": member_membership.pk},
        ),
        {"role": GroupMembership.Role.OWNER},
    )
    assert response.status_code == 302
    member_membership.refresh_from_db()
    assert member_membership.role == GroupMembership.Role.MEMBER


@pytest.mark.django_db
def test_owner_can_promote_member_to_owner(client, owner, member, group):
    member_membership = _membership(group, member)
    client.force_login(owner)
    response = client.post(
        reverse(
            "groups:member_update_role",
            kwargs={"pk": group.pk, "membership_pk": member_membership.pk},
        ),
        {"role": GroupMembership.Role.OWNER},
    )
    assert response.status_code == 302
    member_membership.refresh_from_db()
    assert member_membership.role == GroupMembership.Role.OWNER


@pytest.mark.django_db
def test_cannot_remove_last_owner(client, owner, group):
    owner_membership = _membership(group, owner)
    actor = owner_membership
    assert not can_remove_membership(actor, owner_membership)
    client.force_login(owner)
    response = client.post(
        reverse(
            "groups:member_remove",
            kwargs={"pk": group.pk, "membership_pk": owner_membership.pk},
        )
    )
    assert response.status_code == 302
    assert GroupMembership.objects.filter(pk=owner_membership.pk).exists()


@pytest.mark.django_db
def test_owner_can_remove_co_owner_when_multiple_owners(
    client, owner, other_owner, group
):
    co_membership = GroupMembership.objects.create(
        group=group,
        user=other_owner,
        role=GroupMembership.Role.OWNER,
    )
    client.force_login(owner)
    response = client.post(
        reverse(
            "groups:member_remove",
            kwargs={"pk": group.pk, "membership_pk": co_membership.pk},
        )
    )
    assert response.status_code == 302
    assert not GroupMembership.objects.filter(pk=co_membership.pk).exists()


@pytest.mark.django_db
def test_member_detail_hides_management_ui(client, member, group):
    client.force_login(member)
    content = client.get(reverse("groups:detail", kwargs={"pk": group.pk})).content.decode()
    assert "Add member" not in content
    assert "Add guest" not in content
    assert "Remove" not in content


@pytest.mark.django_db
def test_editor_detail_shows_management_ui(client, editor, group):
    client.force_login(editor)
    content = client.get(reverse("groups:detail", kwargs={"pk": group.pk})).content.decode()
    assert "Add member" in content
    assert "Add guest" in content


@pytest.mark.django_db
def test_remove_guest_player_without_games(client, editor, group):
    from leaderlodge.groups.models import GroupPlayer

    guest = GroupPlayer.objects.create(group=group, display_name="Pat")
    client.force_login(editor)
    response = client.post(
        reverse(
            "groups:player_remove",
            kwargs={"pk": group.pk, "player_pk": guest.pk},
        )
    )
    assert response.status_code == 302
    assert not GroupPlayer.objects.filter(pk=guest.pk).exists()


@pytest.mark.django_db
def test_remove_guest_player_with_games_deactivates(client, editor, group):
    from datetime import date

    from leaderlodge.games.models import Game, GameParticipantResult
    from leaderlodge.groups.models import GroupPlayer

    guest = GroupPlayer.objects.create(group=group, display_name="Pat")
    game = Game.objects.create(
        group=group,
        game_type_code="dominos",
        played_on=date(2024, 1, 15),
        recorded_by=editor,
        player_count=1,
    )
    GameParticipantResult.objects.create(game=game, player=guest)
    client.force_login(editor)
    response = client.post(
        reverse(
            "groups:player_remove",
            kwargs={"pk": group.pk, "player_pk": guest.pk},
        )
    )
    assert response.status_code == 302
    guest.refresh_from_db()
    assert guest.is_active is False
    assert guest.linked_user is None


@pytest.mark.django_db
def test_cannot_remove_active_member_from_roster(client, editor, member, group):
    player = group.players.get(linked_user=member)
    client.force_login(editor)
    response = client.post(
        reverse(
            "groups:player_remove",
            kwargs={"pk": group.pk, "player_pk": player.pk},
        )
    )
    assert response.status_code == 404
    player.refresh_from_db()
    assert player.linked_user_id == member.pk
