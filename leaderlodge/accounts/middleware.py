"""Request middleware for game-type lock/type URL controls."""

from __future__ import annotations

from django.http import HttpRequest, HttpResponse

from leaderlodge.accounts.game_type_url import (
    apply_game_type_url_controls,
    control_params_present,
    redirect_without_control_params,
)


class GameTypeUrlControlMiddleware:
    """Apply ?lock/?l/?type/?t/?unlock; strip lock/unlock from the URL."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if request.method == "GET" and control_params_present(request):
            needs_strip = apply_game_type_url_controls(request)
            if needs_strip:
                return redirect_without_control_params(request)
        return self.get_response(request)
