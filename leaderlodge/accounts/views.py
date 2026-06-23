from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, JsonResponse
from django.middleware.csrf import get_token
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

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
