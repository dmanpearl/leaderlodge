from urllib.parse import urlencode

from django.conf import settings
from django.http import HttpRequest, HttpResponse, HttpResponseNotFound
from django.shortcuts import redirect, render
from django.urls import reverse

from leaderlodge.groups.names import apply_label_overrides, disambiguate_labels

from leaderlodge.accounts.game_selection import (
    all_game_type_codes,
    resolve_game_type_code,
)
from leaderlodge.accounts.group_selection import resolve_view_group
from leaderlodge.core.decorators import demo_or_login_required
from leaderlodge.games.game_size import available_game_sizes, resolve_game_size
from leaderlodge.games.game_type_icons import game_type_icon_url
from leaderlodge.games.models import Game
from leaderlodge.games.registry import get_game_type
from leaderlodge.groups.models import Group, Location
from leaderlodge.groups.permissions import can_invite_roster_player, get_membership
from leaderlodge.groups.services import can_manage_group_members, visible_groups
from leaderlodge.leaderboards.period import (
    LeaderboardPeriod,
    build_leaderboard_query,
    leaderboard_filter_summary,
)
from leaderlodge.leaderboards.game_filters import (
    game_filter_context,
    resolve_leaderboard_game_filters,
)
from leaderlodge.leaderboards.hall_of_fame import (
    GRANULARITY_MONTH,
    GRANULARITY_YEAR,
    build_hall_of_fame_grid,
    build_hall_of_fame_query,
    hall_of_fame_filter_summary,
    resolve_hall_of_fame_granularity,
)
from leaderlodge.insights.context.group import SCOPE_HALL_OF_FAME
from leaderlodge.insights.model_selection import preferred_insight_model_id
from leaderlodge.insights.registry import MODEL_REGISTRY
from leaderlodge.insights.views import insights_feature_enabled, insights_ui_enabled
from leaderlodge.groups.teams import (
    PLAYER_TYPE_CHOICES,
    normalize_player_type,
    player_type_filter_label,
)
from leaderlodge.leaderboards.service import get_player_rank_detail, get_player_rankings


def _game_type_codes_for_group(group: Group) -> list[str]:
    return list(
        Game.objects.filter(group=group)
        .values_list("game_type_code", flat=True)
        .distinct()
        .order_by("game_type_code")
    )


def _leaderboard_game_type_options(
    played_codes: list[str],
) -> list[tuple[str, str, bool]]:
    played_set = frozenset(played_codes)
    return [
        (code, get_game_type(code).name, code not in played_set)
        for code in all_game_type_codes()
    ]


def _resolve_leaderboard_game_type_code(
    request: HttpRequest,
    *,
    played_codes: list[str],
) -> str:
    all_codes = all_game_type_codes()
    requested = request.GET.get("game_type_code", "").strip()
    if requested in all_codes:
        resolve_game_type_code(
            request,
            requested=requested,
            available_codes=all_codes,
        )
        return requested
    return resolve_game_type_code(
        request,
        requested="",
        available_codes=played_codes if played_codes else all_codes,
    )


def _game_size_context(
    group: Group | None,
    game_type_code: str | None,
    request: HttpRequest,
) -> dict:
    if group is None or not game_type_code:
        return {
            "game_size_options": (),
            "selected_game_size": None,
        }

    options = available_game_sizes(
        Game.objects.filter(group=group, game_type_code=game_type_code)
    )
    selected = resolve_game_size(
        request.GET.get("game_size", "").strip(),
        options,
    )
    return {
        "game_size_options": options,
        "selected_game_size": selected,
    }


def _location_choices_for_leaderboard(group: Group | None, game_type_code: str | None):
    if group is None or not game_type_code:
        return Location.objects.none()
    location_ids = (
        Game.objects.filter(group=group, game_type_code=game_type_code)
        .exclude(location_id=None)
        .values_list("location_id", flat=True)
        .distinct()
    )
    return Location.objects.filter(pk__in=location_ids).order_by("name")


def _resolve_leaderboard_location_id(request: HttpRequest, locations) -> int | None:
    raw = (request.GET.get("location") or "").strip()
    if not raw.isdigit():
        return None
    location_id = int(raw)
    if any(loc.pk == location_id for loc in locations):
        return location_id
    return None


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


def _period_context(
    group: Group | None,
    game_type_code: str | None,
    request: HttpRequest,
) -> dict:
    from leaderlodge.leaderboards.period import period_filter_context_from_request

    return period_filter_context_from_request(
        request,
        group=group,
        game_type_code=game_type_code,
    )


def _insights_template_context(request: HttpRequest) -> dict:
    return {
        "insights_enabled": insights_ui_enabled(),
        "insights_ready": insights_feature_enabled(),
        "insight_models": tuple(MODEL_REGISTRY.values()),
        "selected_insight_model": preferred_insight_model_id(request),
    }


@demo_or_login_required
def leaderboard_index(request: HttpRequest) -> HttpResponse:
    groups = list(visible_groups(request.user).order_by("name"))
    requested_group = request.GET.get("group") if "group" in request.GET else None
    selected_group = resolve_view_group(
        request,
        requested=requested_group,
        available_groups=groups,
    )

    played_game_type_codes = (
        _game_type_codes_for_group(selected_group) if selected_group else []
    )
    if selected_group:
        selected_game_type_code = _resolve_leaderboard_game_type_code(
            request,
            played_codes=played_game_type_codes,
        )
    else:
        selected_game_type_code = None

    resolved_group_id = str(selected_group.pk) if selected_group else ""
    period_ctx = _period_context(selected_group, selected_game_type_code, request)
    selected_period = period_ctx["selected_period"]
    game_size_ctx = _game_size_context(
        selected_group,
        selected_game_type_code,
        request,
    )
    selected_game_size = game_size_ctx["selected_game_size"]
    game_filters = resolve_leaderboard_game_filters(
        request.GET,
        game_type_code=selected_game_type_code,
    ).without_shutout_scope()

    if _leaderboard_needs_redirect(
        request,
        resolved_group_id=resolved_group_id,
        resolved_game_type_code=selected_game_type_code,
    ):
        query = build_leaderboard_query(
            group_id=resolved_group_id,
            game_type_code=selected_game_type_code,
            period=selected_period,
            game_size=selected_game_size,
            game_filters=game_filters,
        )
        url = reverse("leaderboards:index")
        if query:
            url = f"{url}?{query}"
        return redirect(url)

    player_type = normalize_player_type(request.GET.get("player_type", ""))
    game_filter_ctx = game_filter_context(
        game_type_code=selected_game_type_code,
        selected_filters=game_filters,
    )
    locations = list(
        _location_choices_for_leaderboard(selected_group, selected_game_type_code)
    )
    selected_location_id = _resolve_leaderboard_location_id(request, locations)
    selected_location = next(
        (loc for loc in locations if loc.pk == selected_location_id),
        None,
    )

    rankings = []
    selected_game_type = None
    if selected_group and selected_game_type_code:
        selected_game_type = get_game_type(selected_game_type_code)
        rankings = get_player_rankings(
            selected_group,
            game_type_code=selected_game_type_code,
            period=selected_period,
            game_size=selected_game_size,
            player_type=player_type,
            location_id=selected_location_id,
            game_filters=game_filters,
        )
        if rankings:
            apply_label_overrides([r.player for r in rankings])

    can_manage_members = bool(selected_group) and can_manage_group_members(
        request.user, selected_group
    )
    invite_eligible_player_ids: set[int] = set()
    if can_manage_members and rankings:
        actor_membership = get_membership(request.user, selected_group)
        invite_eligible_player_ids = {
            row.player.pk
            for row in rankings
            if can_invite_roster_player(actor_membership, row.player, selected_group)
        }

    game_type_options = _leaderboard_game_type_options(played_game_type_codes)
    selected_game_type_has_games = bool(
        selected_game_type_code
        and selected_game_type_code in frozenset(played_game_type_codes)
    )
    period_label = selected_period.display_label()
    leaderboard_query = build_leaderboard_query(
        group_id=resolved_group_id,
        game_type_code=selected_game_type_code or "",
        period=selected_period,
        game_size=selected_game_size,
        player_type=player_type,
        location_id=selected_location_id,
        game_filters=game_filters,
    )
    game_size_label = ""
    if selected_game_size is not None:
        game_size_label = f"{selected_game_size}-player"
    insight_subtitle = (
        f"{selected_game_type.name} · {period_label} · {game_size_label}"
        if selected_game_type and period_label and game_size_label
        else (
            f"{selected_game_type.name} · {game_size_label}"
            if selected_game_type and game_size_label
            else (
                f"{selected_game_type.name} · {period_label}"
                if selected_game_type and period_label
                else (selected_game_type.name if selected_game_type else "")
            )
        )
    )
    player_type_label = player_type_filter_label(player_type)
    location_name = selected_location.name if selected_location else ""
    filter_summary = ""
    if selected_group:
        filter_summary = leaderboard_filter_summary(
            group_name=selected_group.name,
            game_type_name=selected_game_type.name if selected_game_type else None,
            period_label=period_label,
            game_size_label=game_size_label,
            player_type_label=player_type_label,
            location_name=location_name,
            game_filter_labels=game_filter_ctx["game_filter_labels"],
        )

    return render(
        request,
        "leaderboards/leaderboard.html",
        {
            "groups": groups,
            "selected_group": selected_group,
            "game_type_options": game_type_options,
            "played_game_type_codes": played_game_type_codes,
            "selected_game_type_has_games": selected_game_type_has_games,
            "selected_game_type_code": selected_game_type_code,
            "selected_game_type": selected_game_type,
            "selected_game_type_icon_url": (
                game_type_icon_url(selected_game_type_code)
                if selected_game_type_code
                else ""
            ),
            "rankings": rankings,
            "provisional_threshold": settings.LEADERBOARD_PROVISIONAL_THRESHOLD,
            "period_label": period_label,
            "leaderboard_query": leaderboard_query,
            "hall_of_fame_query": build_hall_of_fame_query(
                group_id=resolved_group_id,
                player_type=player_type,
            ),
            "insight_subtitle": insight_subtitle,
            "filter_summary": filter_summary,
            "game_size_label": game_size_label,
            "player_type": player_type,
            "player_type_choices": PLAYER_TYPE_CHOICES,
            "locations": locations,
            "selected_location_id": selected_location_id,
            "selected_location": selected_location,
            "can_manage_members": can_manage_members,
            "invite_eligible_player_ids": invite_eligible_player_ids,
            **period_ctx,
            **game_size_ctx,
            **game_filter_ctx,
            **_insights_template_context(request),
        },
    )


def _hall_of_fame_needs_redirect(
    request: HttpRequest,
    *,
    resolved_group_id: str,
    resolved_granularity: str,
) -> bool:
    requested_group = request.GET.get("group") if "group" in request.GET else None
    requested_granularity = request.GET.get("granularity", "").strip()
    if requested_group is None and resolved_group_id:
        return True
    if (
        requested_group is not None
        and resolved_group_id
        and requested_group.strip() != resolved_group_id
    ):
        return True
    if requested_granularity and requested_granularity != resolved_granularity:
        return True
    if not requested_granularity and resolved_granularity != GRANULARITY_YEAR:
        return True
    return False


@demo_or_login_required
def hall_of_fame(request: HttpRequest) -> HttpResponse:
    groups = list(visible_groups(request.user).order_by("name"))
    requested_group = request.GET.get("group") if "group" in request.GET else None
    selected_group = resolve_view_group(
        request,
        requested=requested_group,
        available_groups=groups,
    )
    resolved_group_id = str(selected_group.pk) if selected_group else ""
    granularity = resolve_hall_of_fame_granularity(
        request.GET.get("granularity", "").strip()
    )

    player_type = normalize_player_type(request.GET.get("player_type", ""))

    if _hall_of_fame_needs_redirect(
        request,
        resolved_group_id=resolved_group_id,
        resolved_granularity=granularity,
    ):
        query = build_hall_of_fame_query(
            group_id=resolved_group_id,
            granularity=granularity,
            player_type=player_type,
        )
        url = reverse("leaderboards:hall_of_fame")
        if query:
            url = f"{url}?{query}"
        return redirect(url)

    grid = None
    filter_summary = ""
    if selected_group:
        hof_label_map = disambiguate_labels(
            list(
                selected_group.players.filter(is_active=True).select_related(
                    "linked_user"
                )
            )
        )
        grid = build_hall_of_fame_grid(
            selected_group,
            granularity=granularity,
            player_type=player_type,
            label_map=hof_label_map,
        )
        filter_summary = hall_of_fame_filter_summary(
            group_name=selected_group.name,
            granularity=granularity,
        )
        type_label = player_type_filter_label(player_type)
        if type_label:
            filter_summary = f"{filter_summary}, {type_label}"

    hall_of_fame_query = build_hall_of_fame_query(
        group_id=resolved_group_id,
        granularity=granularity,
        player_type=player_type,
    )
    leaderboard_query = build_leaderboard_query(
        group_id=resolved_group_id,
        player_type=player_type,
    )

    return render(
        request,
        "leaderboards/hall_of_fame.html",
        {
            "groups": groups,
            "selected_group": selected_group,
            "granularity": granularity,
            "granularity_year": GRANULARITY_YEAR,
            "granularity_month": GRANULARITY_MONTH,
            "grid": grid,
            "filter_summary": filter_summary,
            "hall_of_fame_query": hall_of_fame_query,
            "leaderboard_query": leaderboard_query,
            "period_column_label": (
                "Month" if granularity == GRANULARITY_MONTH else "Year"
            ),
            "selected_period": LeaderboardPeriod.all_time(),
            "insight_scope": SCOPE_HALL_OF_FAME,
            "player_type": player_type,
            "player_type_choices": PLAYER_TYPE_CHOICES,
            **_insights_template_context(request),
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

    period_ctx = _period_context(selected_group, game_type_code, request)
    selected_period = period_ctx["selected_period"]
    game_size_ctx = _game_size_context(selected_group, game_type_code, request)
    selected_game_size = game_size_ctx["selected_game_size"]
    game_filters = resolve_leaderboard_game_filters(
        request.GET,
        game_type_code=game_type_code,
    ).without_shutout_scope()

    detail = get_player_rank_detail(
        selected_group,
        player,
        game_type_code=game_type_code,
        period=selected_period,
        game_size=selected_game_size,
        game_filters=game_filters,
    )
    if detail is None:
        return HttpResponseNotFound()

    all_group_players = list(
        selected_group.players.filter(is_active=True).select_related("linked_user")
    )
    rank_detail_label_map = disambiguate_labels(all_group_players)
    player._label_override = rank_detail_label_map.get(player.pk, player.display_label)
    detail.ranking.player._label_override = rank_detail_label_map.get(
        detail.ranking.player.pk, detail.ranking.player.display_label
    )

    game_type = get_game_type(game_type_code)
    leaderboard_url = (
        f"{reverse('leaderboards:index')}"
        f"?{build_leaderboard_query(group_id=str(selected_group.pk), game_type_code=game_type_code, period=selected_period, game_size=selected_game_size, game_filters=game_filters)}"
    )
    period_label = selected_period.display_label()
    game_size_label = ""
    if selected_game_size is not None:
        game_size_label = f"{selected_game_size}-player"

    insights_enabled = insights_ui_enabled()
    insights_ready = insights_feature_enabled()
    insight_models = tuple(MODEL_REGISTRY.values())
    selected_insight_model = preferred_insight_model_id(request)

    can_manage_members = can_manage_group_members(request.user, selected_group)
    can_invite = can_manage_members and can_invite_roster_player(
        get_membership(request.user, selected_group), player, selected_group
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
            "selected_period": selected_period,
            "period_label": period_label,
            "game_size_label": game_size_label,
            "insights_enabled": insights_enabled,
            "insights_ready": insights_ready,
            "insight_models": insight_models,
            "selected_insight_model": selected_insight_model,
            "can_manage_members": can_manage_members,
            "can_invite": can_invite,
            **period_ctx,
            **game_size_ctx,
        },
    )
