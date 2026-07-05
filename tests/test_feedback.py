import pytest
from django.contrib.auth.models import User
from django.core import mail
from django.urls import reverse

from leaderlodge.feedback.models import Feedback
from leaderlodge.feedback.prompts import GUEST_FEEDBACK_AUTH_MESSAGE


@pytest.fixture
def user(db):
    return User.objects.create_user(
        username="david",
        email="david@example.com",
        password="test-pass-123",
    )


@pytest.mark.django_db
def test_about_page_links_to_feedback_for_authenticated_user(client, user):
    client.force_login(user)
    content = client.get(reverse("core:about")).content.decode()
    assert reverse("feedback:create") in content
    assert "Send feedback" in content


@pytest.mark.django_db
def test_about_page_guest_feedback_prompts_auth(client):
    content = client.get(reverse("core:about")).content.decode()
    assert "Send feedback" in content
    assert GUEST_FEEDBACK_AUTH_MESSAGE in content
    assert "data-guest-auth-trigger" in content


@pytest.mark.django_db
def test_feedback_create_requires_login(client):
    response = client.get(reverse("feedback:create"))
    assert response.status_code == 302
    assert "/accounts/login/" in response.url


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


@pytest.mark.django_db
def test_feedback_create_allows_all_games(client, user):
    client.force_login(user)
    response = client.post(
        reverse("feedback:create"),
        {
            "feedback_type": Feedback.FeedbackType.SUGGESTION,
            "game_type_code": "",
            "title": "Dark mode",
            "description": "Please add a dark theme.",
        },
    )
    assert response.status_code == 302
    feedback = Feedback.objects.get()
    assert feedback.game_type_code == ""
    assert feedback.game_type_label == "All games"


@pytest.mark.django_db
def test_feedback_thanks_requires_login(client, user):
    client.force_login(user)
    response = client.get(reverse("feedback:thanks"))
    assert response.status_code == 200
    assert "Thank you" in response.content.decode()


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
            "game_type_code": "",
            "title": "Nice app",
            "description": "Enjoying LeaderLodge.",
        },
        follow=True,
    )
    assert response.status_code == 200
    assert Feedback.objects.count() == 1
    assert len(mail.outbox) == 0
