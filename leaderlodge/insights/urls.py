from django.urls import path

from leaderlodge.insights import views

app_name = "insights"

urlpatterns = [
    path("player/", views.player_insight, name="player"),
]
