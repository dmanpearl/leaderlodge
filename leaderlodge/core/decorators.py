import functools

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied


def demo_mode_enabled() -> bool:
    return settings.DEMO_MODE_ENABLED


def demo_or_login_required(view_func):
    """Allow anonymous access when demo mode is on and a demo group exists."""

    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if request.user.is_authenticated:
            return view_func(request, *args, **kwargs)
        if demo_mode_enabled():
            from leaderlodge.groups.services import demo_group_exists

            if demo_group_exists():
                return view_func(request, *args, **kwargs)
        return redirect_to_login(request.get_full_path())

    return wrapper


def staff_required(view_func):
    """Require an authenticated staff or superuser account."""

    @login_required
    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        user = request.user
        if not (user.is_staff or user.is_superuser):
            raise PermissionDenied
        return view_func(request, *args, **kwargs)

    return wrapper
