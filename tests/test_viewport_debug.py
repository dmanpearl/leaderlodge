import pytest
from django.contrib.auth.models import User
from django.urls import reverse


@pytest.fixture
def member(db):
    return User.objects.create_user(username="member", password="test-pass-123")


@pytest.fixture
def staff(db):
    return User.objects.create_user(
        username="staffer", password="test-pass-123", is_staff=True
    )


@pytest.mark.django_db
def test_viewport_debug_script_loads_for_staff(client, staff):
    client.force_login(staff)
    content = client.get(reverse("core:dashboard")).content.decode()
    assert "viewport_debug.js" in content


@pytest.mark.django_db
def test_viewport_debug_script_hidden_from_regular_users(client, member):
    client.force_login(member)
    content = client.get(reverse("core:dashboard")).content.decode()
    assert "viewport_debug.js" not in content


@pytest.mark.django_db
def test_viewport_debug_script_hidden_from_anonymous_visitors(client):
    content = client.get(reverse("core:about")).content.decode()
    assert "viewport_debug.js" not in content
