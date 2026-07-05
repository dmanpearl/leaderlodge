from django.urls import path

from leaderlodge.feedback import views

app_name = "feedback"

urlpatterns = [
    path("new/", views.feedback_create, name="create"),
    path("thanks/", views.feedback_thanks, name="thanks"),
]
