import pytest
from django.contrib.auth.models import User
from django.test import override_settings
from django.urls import reverse

from leaderlodge.groups.models import Group
from leaderlodge.insights.ask_examples import (
    get_ask_example,
)


@pytest.fixture
def user(db):
    return User.objects.create_user(username="david", password="test-pass-123")


@override_settings(INSIGHTS_ENABLED=True, OPENAI_API_KEY="test-key")
@pytest.mark.django_db
def test_ask_example_detail_404_for_unknown_slug(client, user):
    client.force_login(user)
    response = client.get(
        reverse("insights:ask_example_detail", kwargs={"slug": "not-a-real-example"})
    )
    assert response.status_code == 404


@override_settings(INSIGHTS_ENABLED=False, OPENAI_API_KEY="", GOOGLE_AI_API_KEY="")
@pytest.mark.django_db
def test_ask_examples_hidden_when_insights_disabled(client, user):
    client.force_login(user)
    response = client.get(reverse("insights:ask_examples"))
    assert response.status_code == 404


@override_settings(INSIGHTS_ENABLED=True, OPENAI_API_KEY="test-key")
@pytest.mark.django_db
def test_ask_example_detail_shows_try_it_for_supported_when_demo_exists(client, user):
    Group.objects.create(name="Demo", is_demo=True, created_by=user)
    client.force_login(user)
    example = get_ask_example("venue-leaders")
    assert example is not None

    response = client.get(
        reverse("insights:ask_example_detail", kwargs={"slug": example.slug})
    )

    assert response.status_code == 200
    content = response.content.decode()
    assert "Try It" in content
    assert "group=" in content
    assert "game_type_code=dominos" in content
    assert "Who+leads+at+Home" in content


@override_settings(INSIGHTS_ENABLED=True, OPENAI_API_KEY="test-key")
@pytest.mark.django_db
def test_ask_example_detail_hides_try_it_for_ui_scenario_example(client, user):
    Group.objects.create(name="Demo", is_demo=True, created_by=user)
    client.force_login(user)
    example = get_ask_example("ui-period-vs-question-intent")
    assert example is not None

    response = client.get(
        reverse("insights:ask_example_detail", kwargs={"slug": example.slug})
    )

    assert response.status_code == 200
    assert "Try It" not in response.content.decode()


@override_settings(INSIGHTS_ENABLED=True, OPENAI_API_KEY="test-key")
@pytest.mark.django_db
def test_ask_page_prefills_question_from_query_string(client, user):
    from leaderlodge.groups.services import add_guest_player, create_group_with_owner
    from tests.test_games import _load_roster_post, _save_game_post

    group = create_group_with_owner(user=user, name="Dom Club")
    add_guest_player(group=group, display_name="Pat")
    client.force_login(user)
    client.post(reverse("games:create"), _load_roster_post(group))
    client.post(reverse("games:create"), _save_game_post(group))
    response = client.get(
        reverse("insights:ask"),
        {
            "group": group.pk,
            "game_type_code": "dominos",
            "question": "How is Nancy doing?",
        },
    )

    assert response.status_code == 200
    assert 'value="How is Nancy doing?"' in response.content.decode()
