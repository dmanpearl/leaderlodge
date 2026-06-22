"""Central group selection backed by per-user and session preferences."""

from __future__ import annotations

from django.http import HttpRequest

from leaderlodge.accounts.ui_settings import get_ui_settings, set_ui_settings
from leaderlodge.groups.models import Group

GROUP_SELECTION_NAMESPACE = "group_selection"
GROUP_ID_KEY = "group_id"
SESSION_GROUP_ID = "group_selection.group_id"


def _saved_group_id(request: HttpRequest) -> str:
    if request.user.is_authenticated:
        return get_ui_settings(request.user, GROUP_SELECTION_NAMESPACE).get(
            GROUP_ID_KEY,
            "",
        )
    return request.session.get(SESSION_GROUP_ID, "")


def _persist_group_id(request: HttpRequest, group_id: str) -> None:
    if request.user.is_authenticated:
        set_ui_settings(
            request.user,
            GROUP_SELECTION_NAMESPACE,
            {GROUP_ID_KEY: group_id},
        )
    else:
        request.session[SESSION_GROUP_ID] = group_id


def preferred_group_id(request: HttpRequest) -> str:
    return _saved_group_id(request)


def _available_group_ids(available_groups) -> list[str]:
    return [str(group.pk) for group in available_groups]


def resolve_group_id(
    request: HttpRequest,
    *,
    requested: str | None,
    available_groups,
) -> str:
    """
    Pick a group id from the query param, saved preference, or first available.

    Always returns a specific group when any are visible. There is no
    "all groups" mode — the active group is persisted for the session/profile.
    """
    available_ids = _available_group_ids(available_groups)
    if not available_ids:
        return ""

    saved = _saved_group_id(request)

    def is_valid(group_id: str) -> bool:
        return group_id in available_ids

    explicit = requested is not None and requested.isdigit() and is_valid(requested)
    if explicit:
        chosen = requested
    elif is_valid(saved):
        chosen = saved
    else:
        chosen = available_ids[0]

    if explicit or not saved:
        _persist_group_id(request, chosen)

    return chosen


def resolve_view_group(
    request: HttpRequest,
    *,
    requested: str | None,
    available_groups,
) -> Group | None:
    group_id = resolve_group_id(
        request,
        requested=requested,
        available_groups=available_groups,
    )
    if not group_id:
        return None
    for group in available_groups:
        if str(group.pk) == group_id:
            return group
    return None


def persist_group_id(request: HttpRequest, group_id: str) -> None:
    _persist_group_id(request, str(group_id))
