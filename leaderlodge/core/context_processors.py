from leaderlodge.core.brand import (
    DEFAULT_META_DESCRIPTION,
    HOME_PAGE_TITLE,
    PIXELMONKS_NAME,
    PIXELMONKS_URL,
    SITE_NAME,
    TAGLINE,
)
from leaderlodge.core.decorators import demo_mode_enabled
from leaderlodge.core.formats import TABLE_DATE_FORMAT
from leaderlodge.feedback.prompts import GUEST_FEEDBACK_AUTH_MESSAGE
from leaderlodge.groups.demo import GUEST_DEMO_PAGE_NOTICE, GUEST_LOGIN_PROMPT
from leaderlodge.groups.services import get_demo_group


def demo_context(request):
    is_visitor = not request.user.is_authenticated
    demo_on = demo_mode_enabled()
    guest_showcase = is_visitor and demo_on and get_demo_group() is not None
    return {
        "demo_mode_enabled": demo_on,
        "demo_group": get_demo_group() if demo_on else None,
        "is_visitor": is_visitor,
        "is_guest_demo": guest_showcase,
        "guest_login_prompt": GUEST_LOGIN_PROMPT if guest_showcase else "",
        "guest_feedback_auth_message": (
            GUEST_FEEDBACK_AUTH_MESSAGE if is_visitor else ""
        ),
        "guest_demo_page_notice": GUEST_DEMO_PAGE_NOTICE if guest_showcase else "",
    }


def table_formats(request):
    return {"table_date_format": TABLE_DATE_FORMAT}


def _resolve_navbar_active_section(request) -> str:
    match = getattr(request, "resolver_match", None)
    if match is None:
        return ""

    namespace = match.namespace or ""
    url_name = match.url_name or ""

    if namespace == "games":
        return "add" if url_name == "create" else "games"
    if namespace == "leaderboards":
        return "leaders"
    if namespace == "insights" and url_name == "ask":
        return "insights"
    if namespace == "groups":
        return "groups"
    if namespace == "core" and url_name in {"about", "about_insights"}:
        return "about"
    return ""


def navbar_context(request):
    from leaderlodge.insights.views import insights_ui_enabled

    active = _resolve_navbar_active_section(request)
    return {
        "navbar_active_section": active,
        "insights_ui_enabled": insights_ui_enabled(),
    }


def brand_context(request):
    return {
        "tagline": TAGLINE,
        "site_name": SITE_NAME,
        "home_page_title": HOME_PAGE_TITLE,
        "default_meta_description": DEFAULT_META_DESCRIPTION,
        "pixelmonks_name": PIXELMONKS_NAME,
        "pixelmonks_url": PIXELMONKS_URL,
    }


def insights_debug_context(request):
    from leaderlodge.insights.views import insights_ui_enabled

    enabled = insights_ui_enabled()
    # Staff-only UI:
    # user = request.user
    # enabled = user.is_authenticated and (user.is_staff or user.is_superuser)
    return {"insights_debug_enabled": enabled}
