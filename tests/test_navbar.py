import pytest
from django.contrib.auth.models import User
from django.urls import reverse


@pytest.fixture
def user(db):
    return User.objects.create_user(username="david", password="test-pass-123")


@pytest.fixture
def staff_user(db):
    return User.objects.create_user(
        username="admin",
        password="test-pass-123",
        is_staff=True,
    )


@pytest.fixture
def superuser(db):
    return User.objects.create_user(
        username="root",
        password="test-pass-123",
        is_superuser=True,
        is_staff=False,
    )


@pytest.mark.django_db
def test_navbar_shows_login_button_for_anonymous(client):
    response = client.get(reverse("accounts:login"))
    content = response.content.decode()

    assert response.status_code == 200
    assert 'href="' in content and reverse("accounts:login") in content
    assert "Login" in content
    assert 'class="bi bi-person navbar-user-icon"' in content
    assert 'id="login-password-toggle"' in content
    assert 'class="bi bi-eye"' in content
    assert "Administration" not in content
    assert "dropdown-toggle" not in content


@pytest.mark.parametrize("account_fixture", ["staff_user", "superuser"])
@pytest.mark.django_db
def test_navbar_shows_admin_for_privileged_user(client, account_fixture, request):
    user = request.getfixturevalue(account_fixture)
    client.force_login(user)
    response = client.get(reverse("core:dashboard"))
    content = response.content.decode()

    assert response.status_code == 200
    assert "Admin" in content
    assert "System Admin" not in content
    assert 'class="bi bi-gear navbar-menu-icon"' in content
    assert reverse("admin:index") in content
    assert "Administration" not in content
    assert ">Dashboard</a>" not in content
    if account_fixture == "staff_user":
        assert content.count(f'href="{reverse("core:dashboard")}"') == 1


@pytest.mark.django_db
def test_navbar_shows_account_dropdown_for_member(client, user):
    client.force_login(user)
    response = client.get(reverse("core:dashboard"))
    content = response.content.decode()

    assert response.status_code == 200
    assert "dropdown-toggle" in content
    assert "david" in content
    assert "System Admin" not in content
    assert 'action="' in content and reverse("accounts:logout") in content
    assert "Logout" in content
    assert 'class="bi bi-box-arrow-right navbar-menu-icon"' in content
    assert "Administration" not in content
    assert ">Dashboard</a>" not in content
    assert 'class="bi bi-house navbar-nav-icon"' in content
    assert 'class="bi bi-plus-lg navbar-nav-icon"' in content
    assert reverse("games:create") in content
    assert "\n              Add\n" in content or ">Add</a>" in content
