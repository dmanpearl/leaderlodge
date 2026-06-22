from django.http import HttpRequest, HttpResponse, HttpResponseNotFound
from django.shortcuts import render
from django.urls import reverse

from leaderlodge.core.decorators import demo_or_login_required
from leaderlodge.games.registry import get_game_type
from leaderlodge.groups.models import Group
from leaderlodge.groups.services import resolve_view_group, visible_groups
from leaderlodge.leaderboards.service import get_player_rank_detail, get_player_rankings


def _game_type_codes_for_group(group: Group) -> list[str]:
    from leaderlodge.games.models import Game

    return list(
        Game.objects.filter(group=group)
        .values_list("game_type_code", flat=True)
        .distinct()
        .order_by("game_type_code")
    )


@demo_or_login_required
def leaderboard_index(request: HttpRequest) -> HttpResponse:
    groups = visible_groups(request.user).order_by("name")
    selected_group = resolve_view_group(request.user, request.GET.get("group"))

    if selected_group is None and groups.count() == 1:
        selected_group = groups.first()

    game_type_codes = (
        _game_type_codes_for_group(selected_group) if selected_group else []
    )
    selected_game_type_code = request.GET.get("game_type_code")
    if selected_game_type_code not in game_type_codes:
        selected_game_type_code = game_type_codes[0] if game_type_codes else None

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
    selected_group = resolve_view_group(request.user, request.GET.get("group"))
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
