from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.middleware.csrf import get_token
from django.shortcuts import redirect, render
from django.utils.http import urlsafe_base64_decode
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from leaderlodge.accounts.email_verification import (
    email_verification_token_generator,
    is_email_verified,
    mark_email_verified,
    send_welcome_email,
)
from leaderlodge.accounts.forms import SignupForm
from leaderlodge.accounts.game_selection import SESSION_GAME_TYPE_CODE
from leaderlodge.accounts.group_selection import SESSION_GROUP_ID
from leaderlodge.accounts.ui_settings import reset_ui_settings


@require_GET
@ensure_csrf_cookie
def csrf_token(request: HttpRequest) -> JsonResponse:
    return JsonResponse({"csrfToken": get_token(request)})


@login_required
@require_POST
def reset_preferences(request: HttpRequest) -> JsonResponse:
    reset_ui_settings(request.user)
    request.session.pop(SESSION_GAME_TYPE_CODE, None)
    request.session.pop(SESSION_GROUP_ID, None)
    return JsonResponse({"ok": True})


@require_http_methods(["GET", "POST"])
def signup(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        return redirect("core:dashboard")

    form = SignupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        try:
            send_welcome_email(request=request, user=user)
            messages.success(
                request,
                "Welcome to LeaderLodge! We sent a confirmation link to your email.",
            )
        except Exception:
            messages.warning(
                request,
                "Your account was created, but we could not send the welcome email. "
                "Use Verify Email in the account menu to try again.",
            )
        return redirect("core:dashboard")

    return render(request, "accounts/signup.html", {"form": form})


def _user_from_uidb64(uidb64: str) -> User | None:
    try:
        uid = urlsafe_base64_decode(uidb64).decode()
        return User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        return None


@require_GET
def verify_email_confirm(request: HttpRequest, uidb64: str, token: str) -> HttpResponse:
    user = _user_from_uidb64(uidb64)
    if user is None or not email_verification_token_generator.check_token(user, token):
        return render(request, "accounts/verify_email_invalid.html", status=400)

    if is_email_verified(user):
        return render(
            request,
            "accounts/verify_email_complete.html",
            {"already_verified": True},
        )

    mark_email_verified(user)
    return render(
        request,
        "accounts/verify_email_complete.html",
        {"already_verified": False},
    )


@login_required
@require_http_methods(["GET", "POST"])
def verify_email(request: HttpRequest) -> HttpResponse:
    if is_email_verified(request.user):
        return render(request, "accounts/verify_email.html", {"verified": True})

    if request.method == "POST":
        try:
            send_welcome_email(request=request, user=request.user)
            messages.success(
                request,
                "We sent a confirmation link to your email address.",
            )
        except Exception:
            messages.error(
                request,
                "We could not send the email right now. Please try again in a few minutes.",
            )
        return redirect("accounts:verify_email")

    return render(request, "accounts/verify_email.html", {"verified": False})
