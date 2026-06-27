from django.urls import path

from leaderlodge.insights import views

app_name = "insights"

urlpatterns = [
    path("player/", views.player_insight, name="player"),
    path("group/", views.group_insight, name="group"),
    path("matchup/", views.matchup_insight, name="matchup"),
]
