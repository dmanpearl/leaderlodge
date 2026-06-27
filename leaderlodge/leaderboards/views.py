from urllib.parse import urlencode

from django.http import HttpRequest, HttpResponse, HttpResponseNotFound
from django.shortcuts import redirect, render
from django.urls import reverse

from leaderlodge.accounts.game_selection import resolve_game_type_code
from leaderlodge.accounts.group_selection import resolve_view_group
from leaderlodge.core.decorators import demo_or_login_required
from leaderlodge.games.game_size import available_game_sizes, resolve_game_size
from leaderlodge.games.models import Game
from leaderlodge.games.registry import get_game_type
from leaderlodge.groups.models import Group
from leaderlodge.groups.services import visible_groups
from leaderlodge.leaderboards.period import (
    LeaderboardPeriod,
    available_leaderboard_periods,
    build_leaderboard_query,
    month_label,
    resolve_leaderboard_period,
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
from leaderlodge.leaderboards.service import get_player_rank_detail, get_player_rankings


def _game_type_codes_for_group(group: Group) -> list[str]:
    return list(
        Game.objects.filter(group=group)
        .values_list("game_type_code", flat=True)
        .distinct()
        .order_by("game_type_code")
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
    if group is None or not game_type_code:
        return {
            "selected_period": LeaderboardPeriod.all_time(),
            "period_year_options": [],
            "period_month_options": [],
        }

    years, months_by_year = available_leaderboard_periods(group, game_type_code)
    selected_period = resolve_leaderboard_period(
        raw_year=request.GET.get("year", "").strip(),
        raw_month=request.GET.get("month", "").strip(),
        available_years=years,
        months_by_year=months_by_year,
    )
    month_options = [
        {"value": month, "label": month_label(month)}
        for month in (
            months_by_year.get(selected_period.year, ())
            if selected_period.year is not None
            else ()
        )
    ]
    return {
        "selected_period": selected_period,
        "period_year_options": years,
        "period_month_options": month_options,
    }


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
    period_ctx = _period_context(selected_group, selected_game_type_code, request)
    selected_period = period_ctx["selected_period"]
    game_size_ctx = _game_size_context(
        selected_group,
        selected_game_type_code,
        request,
    )
    selected_game_size = game_size_ctx["selected_game_size"]

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
            period=selected_period,
            game_size=selected_game_size,
        )

    game_type_options = [(code, get_game_type(code).name) for code in game_type_codes]
    period_label = selected_period.display_label()
    leaderboard_query = build_leaderboard_query(
        group_id=resolved_group_id,
        game_type_code=selected_game_type_code or "",
        period=selected_period,
        game_size=selected_game_size,
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
            "period_label": period_label,
            "leaderboard_query": leaderboard_query,
            "hall_of_fame_query": build_hall_of_fame_query(group_id=resolved_group_id),
            "insight_subtitle": insight_subtitle,
            "game_size_label": game_size_label,
            **period_ctx,
            **game_size_ctx,
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

    if _hall_of_fame_needs_redirect(
        request,
        resolved_group_id=resolved_group_id,
        resolved_granularity=granularity,
    ):
        query = build_hall_of_fame_query(
            group_id=resolved_group_id,
            granularity=granularity,
        )
        url = reverse("leaderboards:hall_of_fame")
        if query:
            url = f"{url}?{query}"
        return redirect(url)

    grid = None
    filter_summary = ""
    if selected_group:
        grid = build_hall_of_fame_grid(selected_group, granularity=granularity)
        filter_summary = hall_of_fame_filter_summary(
            group_name=selected_group.name,
            granularity=granularity,
        )

    hall_of_fame_query = build_hall_of_fame_query(
        group_id=resolved_group_id,
        granularity=granularity,
    )
    leaderboard_query = build_leaderboard_query(group_id=resolved_group_id)

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

    detail = get_player_rank_detail(
        selected_group,
        player,
        game_type_code=game_type_code,
        period=selected_period,
        game_size=selected_game_size,
    )
    if detail is None:
        return HttpResponseNotFound()

    game_type = get_game_type(game_type_code)
    leaderboard_url = (
        f"{reverse('leaderboards:index')}"
        f"?{build_leaderboard_query(group_id=str(selected_group.pk), game_type_code=game_type_code, period=selected_period, game_size=selected_game_size)}"
    )
    period_label = selected_period.display_label()
    game_size_label = ""
    if selected_game_size is not None:
        game_size_label = f"{selected_game_size}-player"

    insights_enabled = insights_ui_enabled()
    insights_ready = insights_feature_enabled()
    insight_models = tuple(MODEL_REGISTRY.values())
    selected_insight_model = preferred_insight_model_id(request)

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
            **period_ctx,
            **game_size_ctx,
        },
    )
