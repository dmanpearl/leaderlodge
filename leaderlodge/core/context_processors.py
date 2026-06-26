from leaderlodge.core.decorators import demo_mode_enabled
from leaderlodge.core.formats import TABLE_DATE_FORMAT
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
    if namespace == "groups":
        return "groups"
    return ""


def navbar_context(request):
    return {"navbar_active_section": _resolve_navbar_active_section(request)}
