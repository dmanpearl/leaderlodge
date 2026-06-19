import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from leaderlodge.groups.models import GroupMembership, GroupPlayer
from leaderlodge.groups.services import create_group_with_owner


@pytest.fixture
def user(db):
    return User.objects.create_user(username="david", password="test-pass-123")


@pytest.fixture
def other_user(db):
    return User.objects.create_user(username="alice", password="test-pass-123")


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
    assert "Record a game to see player standings." in content


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
def test_add_group_member(client, user, other_user, group):
    client.force_login(user)
    response = client.post(
        reverse("groups:member_add", kwargs={"pk": group.pk}),
        {"user": other_user.pk},
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
def test_add_group_member_grants_group_access(client, user, other_user, group):
    client.force_login(user)
    client.post(
        reverse("groups:member_add", kwargs={"pk": group.pk}),
        {"user": other_user.pk},
    )

    client.force_login(other_user)
    response = client.get(reverse("groups:list"))

    assert response.status_code == 200
    assert "Game Night" in response.content.decode()


@pytest.mark.django_db
def test_add_group_member_rejects_existing_member(client, user, group):
    client.force_login(user)
    response = client.post(
        reverse("groups:member_add", kwargs={"pk": group.pk}),
        {"user": user.pk},
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_add_group_member_hidden_from_non_member(client, other_user, group):
    client.force_login(other_user)
    response = client.post(
        reverse("groups:member_add", kwargs={"pk": group.pk}),
        {"user": other_user.pk},
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_add_group_member_links_existing_guest_player(client, user, group):
    nancy = User.objects.create_user(
        username="nmanpearl",
        password="test-pass-123",
        first_name="Nancy",
    )
    guest = GroupPlayer.objects.create(group=group, display_name="Nancy")
    client.force_login(user)
    response = client.post(
        reverse("groups:member_add", kwargs={"pk": group.pk}),
        {"user": nancy.pk},
    )

    assert response.status_code == 302
    guest.refresh_from_db()
    assert guest.linked_user_id == nancy.pk
    assert GroupMembership.objects.filter(group=group, user=nancy).exists()
    assert group.players.filter(display_name__iexact="Nancy").count() == 1
