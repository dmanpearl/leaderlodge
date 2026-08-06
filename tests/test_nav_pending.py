import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_base_includes_nav_pending_bar_and_script(client):
    response = client.get(reverse("core:about"))
    assert response.status_code == 200
    content = response.content.decode()
    assert 'id="nav-pending-bar"' in content
    assert "nav_pending.js" in content
    assert "nav-pending-bar" in content
