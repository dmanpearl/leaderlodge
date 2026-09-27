import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from leaderlodge.groups.locations import normalize_location_name
from leaderlodge.groups.models import Location
from leaderlodge.groups.services import create_group_with_owner


@pytest.fixture
def admin_user(db):
    return User.objects.create_superuser(
        username="admin",
        email="admin@example.com",
        password="test-pass-123",
    )


@pytest.mark.django_db
def test_location_library_admin_rename_with_many_locations(client, admin_user):
    group = create_group_with_owner(user=admin_user, name="Manpearl")
    library = group.location_library
    library.name = "peeps places"
    library.save(update_fields=["name"])

    for index in range(150):
        Location.objects.create(
            library=library,
            name=f"Place {index}",
            normalized_name=normalize_location_name(f"Place {index}"),
        )

    client.force_login(admin_user)
    url = reverse("admin:groups_locationlibrary_change", args=[library.pk])
    response = client.get(url)
    assert response.status_code == 200

    post_data = {
        "name": "Manpearl places",
        "created_by": admin_user.pk,
    }
    response = client.post(url, post_data)
    assert response.status_code == 302, response.content.decode()[:500]
    library.refresh_from_db()
    assert library.name == "Manpearl places"
