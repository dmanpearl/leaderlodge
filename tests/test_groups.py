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
