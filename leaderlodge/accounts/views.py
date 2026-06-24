from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.middleware.csrf import get_token
from django.shortcuts import redirect, render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_http_methods, require_POST

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
        return redirect("core:dashboard")

    return render(request, "accounts/signup.html", {"form": form})
