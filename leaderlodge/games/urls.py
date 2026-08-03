from django.urls import path

from leaderlodge.games import map_views, views

app_name = "games"

urlpatterns = [
    path("", views.game_list, name="list"),
    path("map/", map_views.game_map, name="map"),
    path("new/", views.game_create, name="create"),
    path("reuse-preview/", views.game_reuse_preview, name="reuse_preview"),
    path("matchup/", views.game_matchup, name="matchup"),
    path("<int:pk>/", views.game_detail, name="detail"),
    path("<int:pk>/edit-game/", views.game_edit_game, name="edit_game"),
    path("<int:pk>/delete/", views.game_delete, name="delete"),
]
