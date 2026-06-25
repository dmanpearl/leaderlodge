import pytest
from django.urls import reverse

from leaderlodge.accounts.group_selection import GROUP_ID_KEY, GROUP_SELECTION_NAMESPACE
from leaderlodge.accounts.ui_settings import get_ui_settings, set_ui_settings
from leaderlodge.groups.models import Group
from leaderlodge.groups.services import create_group_with_owner, add_guest_player


@pytest.fixture
def user(db):
    from django.contrib.auth.models import User

    return User.objects.create_user(username="david", password="test-pass-123")


@pytest.fixture
def group(user):
    group = create_group_with_owner(user=user, name="Alpha Club")
    add_guest_player(group=group, display_name="Pat")
    return group


@pytest.fixture
def other_group(user):
    group = create_group_with_owner(user=user, name="Beta Club")
    add_guest_player(group=group, display_name="Sam")
    return group


@pytest.mark.django_db
def test_create_group_then_dashboard_view_all_selects_new_group(
    client, user, group, other_group
):
    set_ui_settings(
        user,
        GROUP_SELECTION_NAMESPACE,
        {GROUP_ID_KEY: str(other_group.pk)},
    )
    client.force_login(user)

    client.post(
        reverse("groups:create"),
        {"name": "Gamma Club", "description": "Newest"},
        follow=True,
    )
    new_group = Group.objects.get(name="Gamma Club")
    assert get_ui_settings(user, GROUP_SELECTION_NAMESPACE)[GROUP_ID_KEY] == str(
        new_group.pk
    )

    dashboard = client.get(reverse("core:dashboard"))
    content = dashboard.content.decode()
    assert f"{reverse('games:list')}?group={new_group.pk}" in content

    games_response = client.get(
        reverse("games:list"),
        {"group": str(new_group.pk)},
        follow=True,
    )
    final_content = games_response.content.decode()
    assert f'value="{new_group.pk}" selected' in final_content
    assert f'value="{other_group.pk}" selected' not in final_content


@pytest.mark.django_db
def test_group_detail_persists_group_selection(client, user, group, other_group):
    set_ui_settings(
        user,
        GROUP_SELECTION_NAMESPACE,
        {GROUP_ID_KEY: str(other_group.pk)},
    )
    client.force_login(user)

    client.get(reverse("groups:detail", kwargs={"pk": group.pk}))

    assert get_ui_settings(user, GROUP_SELECTION_NAMESPACE)[GROUP_ID_KEY] == str(
        group.pk
    )
