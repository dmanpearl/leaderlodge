from django.urls import path

from leaderlodge.insights import views

app_name = "insights"

urlpatterns = [
    path("player/", views.player_insight, name="player"),
    path("group/", views.group_insight, name="group"),
    path("matchup/", views.matchup_insight, name="matchup"),
    path("ask/", views.ask_page, name="ask"),
    path("ask/examples/", views.ask_examples_page, name="ask_examples"),
    path(
        "ask/examples/<slug:slug>/",
        views.ask_example_detail,
        name="ask_example_detail",
    ),
    path("ask/query/", views.ask_query, name="ask_query"),
]
