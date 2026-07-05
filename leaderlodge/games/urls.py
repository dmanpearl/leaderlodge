from django.urls import path

from leaderlodge.games import views

app_name = "games"

urlpatterns = [
    path("", views.game_list, name="list"),
    path("new/", views.game_create, name="create"),
    path("reuse-preview/", views.game_reuse_preview, name="reuse_preview"),
    path("matchup/", views.game_matchup, name="matchup"),
    path("<int:pk>/", views.game_detail, name="detail"),
    path("<int:pk>/edit-scores/", views.game_edit_scores, name="edit_scores"),
]
