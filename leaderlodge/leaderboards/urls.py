from django.urls import path

from leaderlodge.leaderboards import views

app_name = "leaderboards"

urlpatterns = [
    path("", views.leaderboard_index, name="index"),
    path("hall-of-fame/", views.hall_of_fame, name="hall_of_fame"),
    path("detail/", views.rank_detail, name="detail"),
]
