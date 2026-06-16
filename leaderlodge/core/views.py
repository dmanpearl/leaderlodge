from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from leaderlodge.games.models import Game
from leaderlodge.games.registry import get_game_type
from leaderlodge.groups.services import resolve_user_group, user_groups
from leaderlodge.leaderboards.service import get_player_rankings


def _game_type_codes_for_group(group):
    return list(
        Game.objects.filter(group=group)
        .values_list("game_type_code", flat=True)
        .distinct()
        .order_by("game_type_code")
    )


@login_required
def dashboard(request):
    groups = user_groups(request.user).order_by("name")
    default_group = resolve_user_group(request.user, None)
    if default_group is None and groups.count() == 1:
        default_group = groups.first()

    recent_games = (
        Game.objects.filter(group__in=groups)
        .select_related("group", "location")
        .order_by("-played_on", "-created_at")[:5]
    )

    top_rankings = []
    top_rankings_game_type = None
    if default_group:
        codes = _game_type_codes_for_group(default_group)
        if codes:
            top_rankings_game_type = get_game_type(codes[0])
            top_rankings = get_player_rankings(
                default_group,
                game_type_code=codes[0],
            )[:5]

    record_game_url_group = default_group.pk if default_group else None

    return render(
        request,
        "core/dashboard.html",
        {
            "recent_games": recent_games,
            "top_rankings": top_rankings,
            "top_rankings_game_type": top_rankings_game_type,
            "default_group": default_group,
            "record_game_url_group": record_game_url_group,
        },
    )
