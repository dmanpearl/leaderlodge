from django.urls import path

from leaderlodge.core import views

app_name = "core"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("about/", views.about, name="about"),
    path("about/insights/", views.about_insights, name="about_insights"),
    path("about/rank-scoring/", views.about_scoring, name="about_scoring"),
    path("metrics/", views.metrics, name="metrics"),
]
