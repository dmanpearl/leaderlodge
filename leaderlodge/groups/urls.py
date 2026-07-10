from django.urls import path

from leaderlodge.groups import views

app_name = "groups"

urlpatterns = [
    path("", views.group_list, name="list"),
    path("new/", views.group_create, name="create"),
    path("<int:pk>/", views.group_detail, name="detail"),
    path("<int:pk>/edit/", views.group_edit, name="edit"),
    path("<int:pk>/locations/", views.group_locations, name="locations"),
    path(
        "<int:pk>/locations/manage/",
        views.location_manage,
        name="location_manage",
    ),
    path(
        "<int:pk>/locations/<int:loc_pk>/rename/",
        views.location_rename,
        name="location_rename",
    ),
    path(
        "<int:pk>/locations/<int:loc_pk>/combine/",
        views.location_combine,
        name="location_combine",
    ),
    path(
        "<int:pk>/locations/<int:loc_pk>/delete/",
        views.location_delete,
        name="location_delete",
    ),
    path("<int:pk>/players/search/", views.group_players_search, name="players_search"),
    path("<int:pk>/players/add/", views.player_add, name="player_add"),
    path(
        "<int:pk>/players/<int:player_pk>/remove/",
        views.player_remove,
        name="player_remove",
    ),
    path(
        "<int:pk>/players/<int:player_pk>/combine/",
        views.player_combine,
        name="player_combine",
    ),
    path("<int:pk>/members/add/", views.invite_send, name="invite_send"),
    path(
        "<int:pk>/players/<int:player_pk>/invite/",
        views.player_invite,
        name="player_invite",
    ),
    path(
        "<int:pk>/invites/<int:invite_pk>/revoke/",
        views.invite_revoke,
        name="invite_revoke",
    ),
    path("join/<str:token>/", views.invite_accept, name="invite_accept"),
    path(
        "<int:pk>/members/<int:membership_pk>/role/",
        views.member_update_role,
        name="member_update_role",
    ),
    path(
        "<int:pk>/members/<int:membership_pk>/remove/",
        views.member_remove,
        name="member_remove",
    ),
]
