from urllib.parse import urlencode

from django.http import HttpRequest, HttpResponse, HttpResponseNotFound
from django.shortcuts import redirect, render
from django.urls import reverse

from leaderlodge.accounts.game_selection import resolve_game_type_code
from leaderlodge.accounts.group_selection import resolve_view_group
from leaderlodge.core.decorators import demo_or_login_required
from leaderlodge.games.registry import get_game_type
from leaderlodge.groups.models import Group
from leaderlodge.groups.services import visible_groups
from leaderlodge.leaderboards.service import get_player_rank_detail, get_player_rankings


def _game_type_codes_for_group(group: Group) -> list[str]:
    from leaderlodge.games.models import Game

    return list(
        Game.objects.filter(group=group)
        .values_list("game_type_code", flat=True)
        .distinct()
        .order_by("game_type_code")
    )


def _leaderboard_query(*, group_id: str, game_type_code: str | None) -> str:
    params = {}
    if group_id:
        params["group"] = group_id
    if game_type_code:
        params["game_type_code"] = game_type_code
    return urlencode(params)


def _leaderboard_needs_redirect(
    request: HttpRequest,
    *,
    resolved_group_id: str,
    resolved_game_type_code: str | None,
) -> bool:
    requested_group = request.GET.get("group") if "group" in request.GET else None
    requested_game_type = (
        request.GET.get("game_type_code") if "game_type_code" in request.GET else None
    )
    if requested_group is None and resolved_group_id:
        return True
    if requested_game_type is None and resolved_game_type_code:
        return True
    if (
        requested_group is not None
        and resolved_group_id
        and requested_group.strip() != resolved_group_id
    ):
        return True
    if (
        requested_game_type is not None
        and resolved_game_type_code
        and requested_game_type.strip() != resolved_game_type_code
    ):
        return True
    return False


@demo_or_login_required
def leaderboard_index(request: HttpRequest) -> HttpResponse:
    groups = list(visible_groups(request.user).order_by("name"))
    requested_group = request.GET.get("group") if "group" in request.GET else None
    selected_group = resolve_view_group(
        request,
        requested=requested_group,
        available_groups=groups,
    )

    game_type_codes = (
        _game_type_codes_for_group(selected_group) if selected_group else []
    )
    if game_type_codes:
        selected_game_type_code = resolve_game_type_code(
            request,
            requested=request.GET.get("game_type_code", "").strip(),
            available_codes=game_type_codes,
        )
    else:
        selected_game_type_code = None

    resolved_group_id = str(selected_group.pk) if selected_group else ""
    if _leaderboard_needs_redirect(
        request,
        resolved_group_id=resolved_group_id,
        resolved_game_type_code=selected_game_type_code,
    ):
        query = _leaderboard_query(
            group_id=resolved_group_id,
            game_type_code=selected_game_type_code,
        )
        url = reverse("leaderboards:index")
        if query:
            url = f"{url}?{query}"
        return redirect(url)

    rankings = []
    selected_game_type = None
    if selected_group and selected_game_type_code:
        selected_game_type = get_game_type(selected_game_type_code)
        rankings = get_player_rankings(
            selected_group,
            game_type_code=selected_game_type_code,
        )

    game_type_options = [(code, get_game_type(code).name) for code in game_type_codes]

    return render(
        request,
        "leaderboards/leaderboard.html",
        {
            "groups": groups,
            "selected_group": selected_group,
            "game_type_options": game_type_options,
            "selected_game_type_code": selected_game_type_code,
            "selected_game_type": selected_game_type,
            "rankings": rankings,
        },
    )


@demo_or_login_required
def rank_detail(request: HttpRequest) -> HttpResponse:
    groups = list(visible_groups(request.user).order_by("name"))
    requested_group = request.GET.get("group") if "group" in request.GET else None
    selected_group = resolve_view_group(
        request,
        requested=requested_group,
        available_groups=groups,
    )
    game_type_code = request.GET.get("game_type_code")
    player_id = request.GET.get("player")

    if (
        selected_group is None
        or not game_type_code
        or not player_id
        or game_type_code not in _game_type_codes_for_group(selected_group)
    ):
        return HttpResponseNotFound()

    player = selected_group.players.filter(pk=player_id).first()
    if player is None:
        return HttpResponseNotFound()

    detail = get_player_rank_detail(
        selected_group,
        player,
        game_type_code=game_type_code,
    )
    if detail is None:
        return HttpResponseNotFound()

    game_type = get_game_type(game_type_code)
    leaderboard_url = (
        f"{reverse('leaderboards:index')}"
        f"?group={selected_group.pk}&game_type_code={game_type_code}"
    )

    return render(
        request,
        "leaderboards/rank_detail.html",
        {
            "selected_group": selected_group,
            "game_type": game_type,
            "game_type_code": game_type_code,
            "detail": detail,
            "leaderboard_url": leaderboard_url,
        },
    )
