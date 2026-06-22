from django.contrib.auth import views as auth_views
from django.urls import path

from leaderlodge.accounts import views

app_name = "accounts"

urlpatterns = [
    path(
        "login/",
        auth_views.LoginView.as_view(template_name="accounts/login.html"),
        name="login",
    ),
    path(
        "logout/",
        auth_views.LogoutView.as_view(),
        name="logout",
    ),
    path(
        "api/ui-settings/reset/",
        views.reset_preferences,
        name="reset_preferences",
    ),
]
