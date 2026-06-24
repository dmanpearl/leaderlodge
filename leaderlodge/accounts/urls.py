from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy

from leaderlodge.accounts import views
from leaderlodge.accounts.forms import (
    EmailOrUsernameAuthenticationForm,
    StyledPasswordResetForm,
    StyledSetPasswordForm,
)

app_name = "accounts"

urlpatterns = [
    path(
        "login/",
        auth_views.LoginView.as_view(
            template_name="accounts/login.html",
            authentication_form=EmailOrUsernameAuthenticationForm,
        ),
        name="login",
    ),
    path(
        "logout/",
        auth_views.LogoutView.as_view(),
        name="logout",
    ),
    path("signup/", views.signup, name="signup"),
    path(
        "verify-email/",
        views.verify_email,
        name="verify_email",
    ),
    path(
        "verify/<uidb64>/<token>/",
        views.verify_email_confirm,
        name="verify_email_confirm",
    ),
    path(
        "password-reset/",
        auth_views.PasswordResetView.as_view(
            template_name="accounts/password_reset_form.html",
            email_template_name="accounts/password_reset_email.txt",
            subject_template_name="accounts/password_reset_subject.txt",
            form_class=StyledPasswordResetForm,
            success_url=reverse_lazy("accounts:password_reset_done"),
        ),
        name="password_reset",
    ),
    path(
        "password-reset/done/",
        auth_views.PasswordResetDoneView.as_view(
            template_name="accounts/password_reset_done.html",
        ),
        name="password_reset_done",
    ),
    path(
        "reset/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="accounts/password_reset_confirm.html",
            form_class=StyledSetPasswordForm,
            success_url=reverse_lazy("accounts:password_reset_complete"),
        ),
        name="password_reset_confirm",
    ),
    path(
        "reset/done/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="accounts/password_reset_complete.html",
        ),
        name="password_reset_complete",
    ),
    path(
        "api/csrf-token/",
        views.csrf_token,
        name="csrf_token",
    ),
    path(
        "api/ui-settings/reset/",
        views.reset_preferences,
        name="reset_preferences",
    ),
]
