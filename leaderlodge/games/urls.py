from django.urls import path

from leaderlodge.games import views

app_name = "games"

urlpatterns = [
    path("new/", views.game_create, name="create"),
    path("<int:pk>/", views.game_detail, name="detail"),
]
