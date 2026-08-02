import pytest
from django.contrib.auth.models import User
from django.core import mail
from django.urls import reverse

from leaderlodge.accounts.honeypot import honeypot_post_data
from leaderlodge.groups.invites import (
    accept_group_invite,
    create_email_invite,
    create_email_invite_for_guest,
    revoke_group_invite,
)
from leaderlodge.groups.models import GroupInvite, GroupMembership, GroupPlayer
from leaderlodge.groups.services import (
    add_guest_player,
    add_group_member,
    create_group_with_owner,
)


@pytest.fixture
def owner(db):
    return User.objects.create_user(
        username="owner",
        email="owner@example.com",
        password="test-pass-123",
    )


@pytest.fixture
def invitee(db):
    return User.objects.create_user(
        username="alice",
        email="alice@example.com",
        password="test-pass-123",
    )


@pytest.fixture
def group(owner):
    return create_group_with_owner(user=owner, name="Game Night")


@pytest.mark.django_db
def test_create_email_invite_adds_guest_player(group, owner):
    invite = create_email_invite(
        group=group,
        email="newperson@example.com",
        invited_by=owner,
        player_name="New Person",
    )

    assert invite.guest_player is not None
    assert invite.guest_player.display_name == "New Person"
    assert invite.guest_player.linked_user is None
    assert invite.guest_preexisting is False


@pytest.mark.django_db
def test_create_email_invite_defaults_player_name_from_email(group, owner):
    invite = create_email_invite(
        group=group,
        email="john.doe@example.com",
        invited_by=owner,
    )

    assert invite.guest_player.display_name == "John"


@pytest.mark.django_db
def test_accept_email_invite_links_guest_and_adds_membership(group, owner, invitee):
    invite = create_email_invite(
        group=group,
        email=invitee.email,
        invited_by=owner,
        player_name="Alice Guest",
    )
    guest = invite.guest_player

    accept_group_invite(invite=invite, user=invitee, first_name="Alice")

    guest.refresh_from_db()
    assert guest.linked_user_id == invitee.pk
    assert invitee.first_name == "Alice"
    assert GroupMembership.objects.filter(group=group, user=invitee).exists()


@pytest.mark.django_db
def test_accept_notifies_owner_when_name_changes(group, owner, invitee):
    invite = create_email_invite(
        group=group,
        email=invitee.email,
        invited_by=owner,
        player_name="Ali",
    )

    accept_group_invite(invite=invite, user=invitee, first_name="Alice")

    assert len(mail.outbox) == 1
    assert owner.email in mail.outbox[0].to
    assert "Ali" in mail.outbox[0].body
    assert "Alice" in mail.outbox[0].body


@pytest.mark.django_db
def test_revoke_email_invite_removes_guest_without_games(group, owner):
    invite = create_email_invite(
        group=group,
        email="ghost@example.com",
        invited_by=owner,
    )
    guest_pk = invite.guest_player_id

    revoke_group_invite(invite=invite)

    assert not GroupPlayer.objects.filter(pk=guest_pk).exists()


@pytest.mark.django_db
def test_revoke_guest_invite_keeps_preexisting_player(group, owner):
    guest = add_guest_player(group=group, display_name="Pat")
    invite = create_email_invite_for_guest(
        group=group,
        guest_player=guest,
        email="pat@example.com",
        invited_by=owner,
    )

    revoke_group_invite(invite=invite)

    assert GroupPlayer.objects.filter(pk=guest.pk).exists()


@pytest.mark.django_db
def test_invite_send_posts_email(client, owner, group):
    client.force_login(owner)
    response = client.post(
        reverse("groups:invite_send", kwargs={"pk": group.pk}),
        {"email": "friend@example.com", "player_name": "Friend"},
    )

    assert response.status_code == 302
    assert len(mail.outbox) == 1
    assert "friend@example.com" in mail.outbox[0].to
    assert GroupInvite.objects.filter(group=group, email="friend@example.com").exists()


@pytest.mark.django_db
def test_signup_via_invite_auto_joins_group(client, owner, group):
    invite = create_email_invite(
        group=group,
        email="brandnew@example.com",
        invited_by=owner,
        player_name="Brand",
    )
    guest_pk = invite.guest_player_id

    response = client.post(
        f"{reverse('accounts:signup')}?invite={invite.token}",
        honeypot_post_data(
            {
                "invite_token": invite.token,
                "email": "brandnew@example.com",
                "password1": "ComplexPass123!",
                "password2": "ComplexPass123!",
                "first_name": "Brandon",
            }
        ),
        follow=True,
    )

    assert response.status_code == 200
    user = User.objects.get(email="brandnew@example.com")
    assert user.first_name == "Brandon"
    assert GroupMembership.objects.filter(group=group, user=user).exists()
    guest = GroupPlayer.objects.get(pk=guest_pk)
    assert guest.linked_user_id == user.pk
    assert len(mail.outbox) == 2
    assert owner.email in mail.outbox[1].to


@pytest.mark.django_db
def test_player_invite_for_existing_guest(client, owner, group):
    guest = add_guest_player(group=group, display_name="Pat")
    client.force_login(owner)
    response = client.post(
        reverse("groups:player_invite", kwargs={"pk": group.pk, "player_pk": guest.pk}),
        {"email": "pat@example.com"},
    )

    assert response.status_code == 302
    invite = GroupInvite.objects.get(group=group, email="pat@example.com")
    assert invite.guest_player_id == guest.pk
    assert invite.guest_preexisting is True
    assert len(mail.outbox) == 1


@pytest.mark.django_db
def test_player_invite_redirects_to_safe_next(client, owner, group):
    guest = add_guest_player(group=group, display_name="Pat")
    client.force_login(owner)
    leaderboard_url = f"{reverse('leaderboards:index')}?group={group.pk}"
    response = client.post(
        reverse("groups:player_invite", kwargs={"pk": group.pk, "player_pk": guest.pk}),
        {"email": "pat@example.com", "next": leaderboard_url},
    )

    assert response.status_code == 302
    assert response["Location"] == leaderboard_url


@pytest.mark.django_db
def test_player_invite_ignores_unsafe_next(client, owner, group):
    guest = add_guest_player(group=group, display_name="Pat")
    client.force_login(owner)
    response = client.post(
        reverse("groups:player_invite", kwargs={"pk": group.pk, "player_pk": guest.pk}),
        {"email": "pat@example.com", "next": "//evil.example.com/steal"},
    )

    assert response.status_code == 302
    assert response["Location"] == reverse("groups:detail", kwargs={"pk": group.pk})


@pytest.mark.django_db
def test_player_invite_defaults_to_group_detail_without_next(client, owner, group):
    guest = add_guest_player(group=group, display_name="Pat")
    client.force_login(owner)
    response = client.post(
        reverse("groups:player_invite", kwargs={"pk": group.pk, "player_pk": guest.pk}),
        {"email": "pat@example.com"},
    )

    assert response.status_code == 302
    assert response["Location"] == reverse("groups:detail", kwargs={"pk": group.pk})


@pytest.mark.django_db
def test_cannot_invite_duplicate_pending_email(client, owner, group):
    client.force_login(owner)
    first = client.post(
        reverse("groups:invite_send", kwargs={"pk": group.pk}),
        {"email": "friend@example.com", "player_name": "Friend"},
    )
    assert first.status_code == 302

    response = client.post(
        reverse("groups:invite_send", kwargs={"pk": group.pk}),
        {"email": "friend@example.com", "player_name": "Friend Again"},
    )
    assert response.status_code == 400
    assert "already pending" in response.content.decode()
    assert (
        GroupInvite.objects.filter(
            group=group,
            email="friend@example.com",
            revoked_at__isnull=True,
        ).count()
        == 1
    )


@pytest.mark.django_db
def test_cannot_invite_member_email(client, owner, group, invitee):
    add_group_member(group=group, user=invitee)
    client.force_login(owner)
    response = client.post(
        reverse("groups:invite_send", kwargs={"pk": group.pk}),
        {"email": invitee.email, "player_name": "Alice"},
    )
    assert response.status_code == 400
    assert "already belongs to a group member" in response.content.decode()


@pytest.mark.django_db
def test_join_page_creates_account_and_joins_group(client, owner, group):
    invite = create_email_invite(
        group=group,
        email="brandnew@example.com",
        invited_by=owner,
        player_name="Brand",
    )
    guest_pk = invite.guest_player_id

    response = client.post(
        reverse("groups:invite_accept", kwargs={"token": invite.token}),
        honeypot_post_data(
            {
                "email": "brandnew@example.com",
                "first_name": "Brandon",
                "last_name": "New",
                "password1": "ComplexPass123!",
                "password2": "ComplexPass123!",
            }
        ),
        follow=True,
    )

    assert response.status_code == 200
    user = User.objects.get(email="brandnew@example.com")
    assert user.first_name == "Brandon"
    assert user.last_name == "New"
    assert GroupMembership.objects.filter(group=group, user=user).exists()
    guest = GroupPlayer.objects.get(pk=guest_pk)
    assert guest.linked_user_id == user.pk
    assert len(mail.outbox) == 2
