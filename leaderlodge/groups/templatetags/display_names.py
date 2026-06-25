from django import template

from leaderlodge.groups.names import format_user_display_name

register = template.Library()


@register.filter
def user_display_name(user) -> str:
    if user is None:
        return ""
    return format_user_display_name(user)


@register.filter
def user_primary_label(user) -> str:
    """First name when set, otherwise username."""
    if user is None:
        return ""
    first = (getattr(user, "first_name", None) or "").strip()
    if first:
        return first
    return user.get_username()


@register.filter
def user_shows_username_suffix(user) -> bool:
    if user is None:
        return False
    first = (getattr(user, "first_name", None) or "").strip()
    if not first:
        return False
    return first.lower() != user.get_username().lower()
