import re

import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from leaderlodge.groups.services import add_guest_player, create_group_with_owner


@pytest.mark.django_db
def test_record_game_page_shows_h1_title(client):
    user = User.objects.create_user(username="titleuser", password="test-pass-123")
    group = create_group_with_owner(user=user, name="Club")
    add_guest_player(group=group, display_name="Pat")
    client.force_login(user)

    response = client.get(reverse("games:create"))
    assert response.status_code == 200
    assert response.context["record_game_heading"] == "Record Game"
    match = re.search(
        r"<h1[^>]*>\s*(.*?)\s*</h1>",
        response.content.decode(),
        re.S,
    )
    assert match is not None
    assert match.group(1) == "Record Game"

    redirect = client.get("/?lock=dominos")
    assert redirect.status_code == 302
    client.get(redirect.url)

    locked = client.get(reverse("games:create"))
    assert locked.status_code == 200
    assert locked.context["record_game_heading"] == "Dominos - Record Game"
    assert locked.context["record_game_heading_icon_url"]
    content = locked.content.decode()
    match = re.search(
        r"<h1[^>]*>\s*(.*?)\s*</h1>",
        content,
        re.S,
    )
    assert match is not None
    assert match.group(1) == "Dominos - Record Game"
    assert "game-detail-title-icon" in content
