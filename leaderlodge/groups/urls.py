from django.urls import path

from leaderlodge.groups import views

app_name = "groups"

urlpatterns = [
    path("", views.group_list, name="list"),
    path("new/", views.group_create, name="create"),
    path("<int:pk>/", views.group_detail, name="detail"),
    path("<int:pk>/locations/", views.group_locations, name="locations"),
    path("<int:pk>/players/add/", views.player_add, name="player_add"),
    path("<int:pk>/members/add/", views.member_add, name="member_add"),
]
