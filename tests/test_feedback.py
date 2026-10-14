import pytest
from django.contrib.auth.models import User
from django.core import mail
from django.urls import reverse

from leaderlodge.feedback.items import (
    FEEDBACK_ITEM_AI_GAME_ENTRY,
    FEEDBACK_ITEM_LOCATION,
    FEEDBACK_ITEM_OTHER,
    FEEDBACK_ITEM_USER_ACCOUNTS,
    feedback_item_choices,
    feedback_item_label,
)
from leaderlodge.feedback.models import Feedback


@pytest.fixture
def user(db):
    return User.objects.create_user(
        username="david",
        email="david@example.com",
        password="test-pass-123",
    )


@pytest.mark.django_db
def test_feedback_create_requires_login(client):
    response = client.get(reverse("feedback:create"))
    assert response.status_code == 302
    assert reverse("accounts:login") in response.url
    assert "next=" in response.url


@pytest.mark.django_db
def test_feedback_form_item_field_and_choices(client, user):
    client.force_login(user)
    page = client.get(reverse("feedback:create"))
    content = page.content.decode()
    assert page.status_code == 200
    assert ">Item</label>" in content or 'for="id_game_type_code"' in content
    assert "All games" not in content
    assert ">Location</option>" in content
    assert ">User Accounts</option>" in content
    assert ">Groups</option>" in content
    assert ">Leaderboards</option>" in content
    assert ">AI game entry</option>" in content
    assert ">Dominos</option>" in content
    assert ">Other</option>" in content
    assert 'value="other" selected' in content

    labels = [label for _code, label in feedback_item_choices()]
    assert labels[0] == "Other"
    assert labels.index("Location") < labels.index("Dominos")
    assert labels.index("AI game entry") < labels.index("Dominos")


@pytest.mark.django_db
def test_feedback_create_submits_and_emails_user(client, user):
    client.force_login(user)
    response = client.post(
        reverse("feedback:create"),
        {
            "feedback_type": Feedback.FeedbackType.BUG,
            "game_type_code": "dominos",
            "title": "Score did not save",
            "description": "After editing a game, the score reverted on refresh.",
        },
    )
    assert response.status_code == 302
    assert response.url == reverse("feedback:thanks")

    feedback = Feedback.objects.get()
    assert feedback.user_id == user.pk
    assert feedback.feedback_type == Feedback.FeedbackType.BUG
    assert feedback.game_type_code == "dominos"
    assert feedback.title == "Score did not save"
    assert feedback.status == Feedback.Status.NEW
    assert feedback.priority == Feedback.Priority.NORMAL
    assert feedback.is_visible is False
    assert feedback.is_approved is False
    assert feedback.assigned_to_id is None

    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == ["david@example.com"]
    assert "Score did not save" in mail.outbox[0].body
    assert "Item: Dominos" in mail.outbox[0].body


@pytest.mark.django_db
def test_feedback_create_defaults_item_to_other(client, user):
    client.force_login(user)
    response = client.post(
        reverse("feedback:create"),
        {
            "feedback_type": Feedback.FeedbackType.FEATURE,
            "title": "Dark mode",
            "description": "",
        },
    )
    assert response.status_code == 302
    feedback = Feedback.objects.get()
    assert feedback.game_type_code == FEEDBACK_ITEM_OTHER
    assert feedback_item_label(feedback.game_type_code) == "Other"


@pytest.mark.django_db
def test_feedback_create_allows_empty_details(client, user):
    client.force_login(user)
    page = client.get(reverse("feedback:create"))
    content = page.content.decode()
    assert page.status_code == 200
    assert "(optional)" in content
    assert 'id="id_description"' in content
    desc_tag = content.split('id="id_description"', 1)[0].rsplit("<", 1)[-1]
    assert "required" not in desc_tag

    response = client.post(
        reverse("feedback:create"),
        {
            "feedback_type": Feedback.FeedbackType.FEATURE,
            "game_type_code": FEEDBACK_ITEM_LOCATION,
            "title": "Map pin drift",
            "description": "",
        },
    )
    assert response.status_code == 302
    assert response.url == reverse("feedback:thanks")
    feedback = Feedback.objects.get()
    assert feedback.title == "Map pin drift"
    assert feedback.description == ""
    assert feedback.game_type_code == FEEDBACK_ITEM_LOCATION


@pytest.mark.django_db
def test_feedback_item_labels_for_app_areas():
    assert feedback_item_label(FEEDBACK_ITEM_USER_ACCOUNTS) == "User Accounts"
    assert feedback_item_label(FEEDBACK_ITEM_AI_GAME_ENTRY) == "AI game entry"
    assert feedback_item_label("") == "Other"


@pytest.mark.django_db
def test_feedback_create_without_email_still_saves(client, db):
    user = User.objects.create_user(
        username="noemail",
        email="",
        password="test-pass-123",
    )
    client.force_login(user)
    response = client.post(
        reverse("feedback:create"),
        {
            "feedback_type": Feedback.FeedbackType.COMMENT,
            "game_type_code": FEEDBACK_ITEM_OTHER,
            "title": "Nice app",
            "description": "Enjoying LeaderLodge.",
        },
        follow=True,
    )
    assert response.status_code == 200
    assert Feedback.objects.count() == 1
    assert len(mail.outbox) == 0
