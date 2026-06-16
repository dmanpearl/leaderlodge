from django.urls import path

from leaderlodge.games import views

app_name = "games"

urlpatterns = [
    path("", views.game_list, name="list"),
    path("new/", views.game_create, name="create"),
    path("<int:pk>/", views.game_detail, name="detail"),
]
