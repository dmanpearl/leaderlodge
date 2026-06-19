from django.urls import path

from leaderlodge.leaderboards import views

app_name = "leaderboards"

urlpatterns = [
    path("", views.leaderboard_index, name="index"),
    path("detail/", views.rank_detail, name="detail"),
]
