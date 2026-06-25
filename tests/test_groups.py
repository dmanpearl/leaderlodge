import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from leaderlodge.accounts.group_selection import GROUP_ID_KEY, GROUP_SELECTION_NAMESPACE
from leaderlodge.accounts.ui_settings import get_ui_settings
from leaderlodge.groups.models import Group, GroupMembership, GroupPlayer
from leaderlodge.groups.services import create_group_with_owner


@pytest.fixture
def user(db):
    return User.objects.create_user(username="david", password="test-pass-123")


@pytest.fixture
def other_user(db):
    return User.objects.create_user(
        username="alice",
        email="alice@example.com",
        password="test-pass-123",
    )


@pytest.fixture
def group(user):
    return create_group_with_owner(
        user=user,
        name="Game Night",
        description="Tuesday regulars",
    )


@pytest.mark.django_db
def test_create_group_with_owner(user):
    group = create_group_with_owner(user=user, name="Domino Club")

    assert group.created_by == user
    assert GroupMembership.objects.filter(
        group=group,
        user=user,
        role=GroupMembership.Role.OWNER,
    ).exists()
    assert GroupPlayer.objects.filter(
        group=group,
        linked_user=user,
        display_name="david",
    ).exists()


@pytest.mark.django_db
def test_group_list_shows_member_groups(client, user, group):
    client.force_login(user)
    response = client.get(reverse("groups:list"))

    assert response.status_code == 200
    assert "Game Night" in response.content.decode()


@pytest.mark.django_db
def test_group_list_excludes_non_member_groups(client, user, other_user, group):
    client.force_login(other_user)
    response = client.get(reverse("groups:list"))

    assert response.status_code == 200
    assert "Game Night" not in response.content.decode()


@pytest.mark.django_db
def test_group_create_persists_group_selection(client, user, group):
    client.force_login(user)
    response = client.post(
        reverse("groups:create"),
        {"name": "New Group", "description": "Test"},
    )

    assert response.status_code == 302
    new_group = Group.objects.get(name="New Group")
    assert get_ui_settings(user, GROUP_SELECTION_NAMESPACE)[GROUP_ID_KEY] == str(
        new_group.pk
    )

    games_response = client.get(reverse("games:list"))
    assert games_response.status_code == 302
    assert f"group={new_group.pk}" in games_response.url


@pytest.mark.django_db
def test_group_list_shows_full_description(client, user, group):
    group.description = (
        "Test group with example game data. Login and use '+ Create Group' "
        "to add your own and start logging game scores."
    )
    group.save(update_fields=["description"])
    client.force_login(user)
    content = client.get(reverse("groups:list")).content.decode()

    assert "Test group with example game data" in content
    assert "start logging game scores" in content
    assert "Create Group" in content
    assert "…" not in content


@pytest.mark.django_db
def test_owner_can_edit_group(client, user, group):
    client.force_login(user)
    response = client.post(
        reverse("groups:edit", kwargs={"pk": group.pk}),
        {"name": "Renamed Night", "description": "Updated notes"},
    )

    assert response.status_code == 302
    group.refresh_from_db()
    assert group.name == "Renamed Night"
    assert group.description == "Updated notes"


@pytest.mark.django_db
def test_member_cannot_edit_group(client, user, other_user, group):
    from leaderlodge.groups.services import add_group_member

    add_group_member(group=group, user=other_user)
    client.force_login(other_user)
    response = client.get(reverse("groups:edit", kwargs={"pk": group.pk}))

    assert response.status_code == 404


@pytest.mark.django_db
def test_group_create(client, user):
    client.force_login(user)
    response = client.post(
        reverse("groups:create"),
        {"name": "New Group", "description": "Test"},
    )

    assert response.status_code == 302
    assert GroupMembership.objects.filter(
        user=user,
        group__name="New Group",
        role=GroupMembership.Role.OWNER,
    ).exists()


@pytest.mark.django_db
def test_group_detail_for_member(client, user, group):
    client.force_login(user)
    response = client.get(reverse("groups:detail", kwargs={"pk": group.pk}))

    assert response.status_code == 200
    content = response.content.decode()
    assert "Game Night" in content
    assert "david" in content
    assert "Player roster" in content
    assert "david" in content


@pytest.mark.django_db
def test_group_detail_hidden_from_non_member(client, other_user, group):
    client.force_login(other_user)
    response = client.get(reverse("groups:detail", kwargs={"pk": group.pk}))

    assert response.status_code == 404


@pytest.mark.django_db
def test_add_guest_player(client, user, group):
    client.force_login(user)
    response = client.post(
        reverse("groups:player_add", kwargs={"pk": group.pk}),
        {"display_name": "Pat"},
    )

    assert response.status_code == 302
    assert group.players.filter(display_name="Pat", linked_user__isnull=True).exists()


@pytest.mark.django_db
def test_add_guest_player_duplicate_name(client, user, group):
    group.players.create(display_name="Pat")
    client.force_login(user)
    response = client.post(
        reverse("groups:player_add", kwargs={"pk": group.pk}),
        {"display_name": "Pat"},
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_accept_invite_adds_group_member(client, user, other_user, group):
    from leaderlodge.groups.invites import create_email_invite

    invite = create_email_invite(
        group=group,
        email=other_user.email,
        invited_by=user,
    )
    client.force_login(other_user)
    response = client.post(
        reverse("groups:invite_accept", kwargs={"token": invite.token}),
        {"first_name": "Alice"},
    )

    assert response.status_code == 302
    assert GroupMembership.objects.filter(
        group=group,
        user=other_user,
        role=GroupMembership.Role.MEMBER,
    ).exists()
    assert GroupPlayer.objects.filter(
        group=group,
        linked_user=other_user,
    ).exists()


@pytest.mark.django_db
def test_accept_invite_grants_group_access(client, user, other_user, group):
    from leaderlodge.groups.invites import create_email_invite

    invite = create_email_invite(
        group=group,
        email=other_user.email,
        invited_by=user,
    )
    client.force_login(other_user)
    client.post(
        reverse("groups:invite_accept", kwargs={"token": invite.token}),
        {"first_name": "Alice"},
    )

    response = client.get(reverse("groups:list"))

    assert response.status_code == 200
    assert "Game Night" in response.content.decode()


@pytest.mark.django_db
def test_invite_send_rejects_existing_member(client, user, group):
    client.force_login(user)
    response = client.post(
        reverse("groups:invite_send", kwargs={"pk": group.pk}),
        {"email": user.email},
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_invite_send_hidden_from_non_member(client, other_user, group):
    client.force_login(other_user)
    response = client.post(
        reverse("groups:invite_send", kwargs={"pk": group.pk}),
        {"email": "other@example.com"},
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_accept_invite_links_guest_player(client, user, group):
    from leaderlodge.groups.invites import create_email_invite

    nancy = User.objects.create_user(
        username="nmanpearl",
        email="nancy@example.com",
        password="test-pass-123",
        first_name="Nancy",
    )
    invite = create_email_invite(
        group=group,
        email=nancy.email,
        invited_by=user,
        player_name="Nancy",
    )
    guest_pk = invite.guest_player_id
    client.force_login(nancy)
    response = client.post(
        reverse("groups:invite_accept", kwargs={"token": invite.token}),
        {"first_name": "Nancy"},
    )

    assert response.status_code == 302
    guest = GroupPlayer.objects.get(pk=guest_pk)
    assert guest.linked_user_id == nancy.pk
    assert GroupMembership.objects.filter(group=group, user=nancy).exists()
    assert group.players.filter(display_name__iexact="Nancy").count() == 1
