"""HTTP views for AI insights."""

from __future__ import annotations

import json
from typing import Any

from django.conf import settings
from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST

from leaderlodge.accounts.game_selection import resolve_game_type_code
from leaderlodge.accounts.group_selection import resolve_view_group
from leaderlodge.core.decorators import demo_or_login_required
from leaderlodge.games.registry import get_game_type
from leaderlodge.groups.services import visible_groups
from leaderlodge.insights.ask_examples import (
    get_ask_example,
    group_ask_examples_by_reliability,
    try_it_url_for_example,
    try_it_urls_by_slug,
)
from leaderlodge.insights.access import (
    InsightAccessError,
    game_type_codes_for_group,
    resolve_ask_target,
    resolve_group_insight_target,
    resolve_matchup_insight_target,
    resolve_player_insight_target,
)
from leaderlodge.insights.context.group import (
    GroupInsightContextError,
    SCOPE_HALL_OF_FAME,
    SCOPE_LEADERBOARD,
    build_group_insight_context,
)
from leaderlodge.insights.context.matchup import (
    MatchupInsightContextError,
    build_matchup_insight_context,
)
from leaderlodge.insights.context.player import (
    InsightContextError,
    build_player_insight_context,
)
from leaderlodge.insights.debug import (
    build_contextual_insight_debug,
    request_include_debug,
)
from leaderlodge.insights.exceptions import InsightRateLimitExceeded
from leaderlodge.insights.model_selection import (
    persist_insight_model_id,
    preferred_insight_model_id,
)
from leaderlodge.insights.providers.base import InsightProviderError
from leaderlodge.insights.prompts import (
    ASK_SYSTEM_PROMPT,
    GROUP_INSIGHT_SYSTEM_PROMPT,
    MATCHUP_INSIGHT_SYSTEM_PROMPT,
    PLAYER_INSIGHT_SYSTEM_PROMPT,
    PRESET_CUSTOM,
    render_ask_user_message,
    render_group_user_message,
    render_matchup_user_message,
    render_user_message,
    resolve_group_preset,
    resolve_matchup_preset,
    resolve_preset,
    sanitize_custom_question,
)
from leaderlodge.leaderboards.hall_of_fame import resolve_hall_of_fame_granularity
from leaderlodge.insights.rate_limit import (
    check_insight_rate_limit,
    record_insight_usage,
)
from leaderlodge.insights.registry import MODEL_REGISTRY, resolve_model_slug
from leaderlodge.insights.service import (
    AskResult,
    InsightResult,
    generate_ask_response,
    generate_group_insight,
    generate_matchup_insight,
    generate_player_insight,
)
from leaderlodge.insights.tools.players import (
    build_ask_player_roster,
    build_question_player_hints,
)
from leaderlodge.insights.tools.scope import AskScope
from leaderlodge.leaderboards.period import (
    LeaderboardPeriod,
    available_leaderboard_periods,
    leaderboard_filter_summary,
    month_label,
    resolve_leaderboard_period,
)


def _configured_api_key(name: str) -> str:
    return (getattr(settings, name, "") or "").strip()


def insights_ui_enabled() -> bool:
    """Show Insights UI when enabled or when API keys are present."""
    if getattr(settings, "INSIGHTS_ENABLED", False):
        return True
    return bool(
        _configured_api_key("OPENAI_API_KEY")
        or _configured_api_key("GOOGLE_AI_API_KEY")
    )


def insights_feature_enabled() -> bool:
    if not getattr(settings, "INSIGHTS_ENABLED", False):
        return False
    return bool(
        _configured_api_key("OPENAI_API_KEY")
        or _configured_api_key("GOOGLE_AI_API_KEY")
    )


def _parse_json_body(request: HttpRequest) -> dict | None:
    if not request.body:
        return {}
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def _insight_meta(result: InsightResult, context: dict[str, Any]) -> dict[str, Any]:
    data_quality = context.get("data_quality", {})
    scope = context.get("scope")
    meta: dict[str, Any] = {
        "model": result.model_slug,
        "model_label": MODEL_REGISTRY[result.model_slug].label,
        "provider": result.provider,
        "prompt_version": result.prompt_version,
        "context_schema_version": result.context_schema_version,
        "cached": result.cached,
        "input_tokens": result.input_tokens,
        "output_tokens": result.output_tokens,
    }
    if scope:
        meta["scope"] = scope

    if scope == SCOPE_HALL_OF_FAME:
        meta["period_count"] = data_quality.get("period_count", 0)
        meta["granularity_label"] = context.get("granularity_label", "Years")
        return meta

    games_in_period = data_quality.get("games_in_period")
    if games_in_period is None:
        games_in_period = data_quality.get("total_weighted_games")
    if games_in_period is not None:
        meta["games_in_period"] = games_in_period
    return meta


def _insight_json_response(
    *,
    result: InsightResult,
    context: dict[str, Any],
    debug: dict[str, Any] | None = None,
) -> JsonResponse:
    body: dict[str, Any] = {
        "markdown": result.markdown,
        "html": result.html,
        "meta": _insight_meta(result, context),
    }
    if debug is not None:
        body["debug"] = debug
    return JsonResponse(body)


@demo_or_login_required
@require_POST
def player_insight(request: HttpRequest) -> HttpResponse:
    if not insights_feature_enabled():
        return JsonResponse({"error": "Insights are not enabled."}, status=404)

    payload = _parse_json_body(request)
    if payload is None:
        return JsonResponse({"error": "Invalid JSON body."}, status=400)

    group_id = str(payload.get("group_id", "")).strip()
    player_id = str(payload.get("player_id", "")).strip()
    game_type_code = str(payload.get("game_type_code", "")).strip()
    preset = resolve_preset(str(payload.get("preset", "")).strip())
    question = str(payload.get("question", "")).strip()
    model_slug = resolve_model_slug(str(payload.get("model", "")).strip())

    if not group_id or not player_id or not game_type_code:
        return JsonResponse({"error": "Missing required fields."}, status=400)
    if preset == PRESET_CUSTOM and not question.strip():
        return JsonResponse({"error": "A custom question is required."}, status=400)

    try:
        group, player, game_type_code, period = resolve_player_insight_target(
            request,
            user=request.user,
            group_id=group_id,
            player_id=player_id,
            game_type_code=game_type_code,
            raw_year=str(payload.get("year", "")),
            raw_month=str(payload.get("month", "")),
        )
    except InsightAccessError as exc:
        return JsonResponse({"error": str(exc)}, status=403)

    try:
        check_insight_rate_limit(request, user=request.user, model_slug=model_slug)
    except InsightRateLimitExceeded as exc:
        response = JsonResponse(
            {
                "error": "Rate limit exceeded.",
                "scope": exc.scope,
                "window": exc.window,
                "limit": exc.limit,
            },
            status=429,
        )
        response["Retry-After"] = str(exc.retry_after_seconds)
        return response

    try:
        context = build_player_insight_context(
            group,
            player,
            game_type_code=game_type_code,
            period=period,
        )
    except InsightContextError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    include_debug = request_include_debug(request.user, payload)

    try:
        result = generate_player_insight(
            context=context,
            preset=preset,
            question=question,
            model_slug=model_slug,
            skip_cache=bool(payload.get("refresh")) or include_debug,
        )
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    except InsightProviderError as exc:
        return JsonResponse({"error": str(exc)}, status=502)

    if not result.cached:
        record_insight_usage(request, user=request.user, model_slug=model_slug)

    persist_insight_model_id(request, model_slug)

    debug = None
    if include_debug:
        resolved_preset = resolve_preset(preset)
        debug = build_contextual_insight_debug(
            mode="player",
            system_prompt=PLAYER_INSIGHT_SYSTEM_PROMPT,
            context=context,
            preset=resolved_preset,
            question=question,
            user_message=render_user_message(
                context=context,
                preset=preset,
                question=question,
            ),
        )

    return _insight_json_response(result=result, context=context, debug=debug)


@demo_or_login_required
@require_POST
def group_insight(request: HttpRequest) -> HttpResponse:
    if not insights_feature_enabled():
        return JsonResponse({"error": "Insights are not enabled."}, status=404)

    payload = _parse_json_body(request)
    if payload is None:
        return JsonResponse({"error": "Invalid JSON body."}, status=400)

    group_id = str(payload.get("group_id", "")).strip()
    scope = str(payload.get("scope", "")).strip()
    game_type_code = str(payload.get("game_type_code", "")).strip()
    preset = resolve_group_preset(str(payload.get("preset", "")).strip(), scope=scope)
    question = str(payload.get("question", "")).strip()
    model_slug = resolve_model_slug(str(payload.get("model", "")).strip())
    granularity = resolve_hall_of_fame_granularity(
        str(payload.get("granularity", "")).strip()
    )

    if not group_id or not scope:
        return JsonResponse({"error": "Missing required fields."}, status=400)
    if preset == PRESET_CUSTOM and not question.strip():
        return JsonResponse({"error": "A custom question is required."}, status=400)

    try:
        group, resolved_scope, period, resolved_game_type_code = (
            resolve_group_insight_target(
                request,
                user=request.user,
                group_id=group_id,
                scope=scope,
                game_type_code=game_type_code,
                raw_year=str(payload.get("year", "")),
                raw_month=str(payload.get("month", "")),
                granularity=granularity,
            )
        )
    except InsightAccessError as exc:
        return JsonResponse({"error": str(exc)}, status=403)

    try:
        check_insight_rate_limit(request, user=request.user, model_slug=model_slug)
    except InsightRateLimitExceeded as exc:
        response = JsonResponse(
            {
                "error": "Rate limit exceeded.",
                "scope": exc.scope,
                "window": exc.window,
                "limit": exc.limit,
            },
            status=429,
        )
        response["Retry-After"] = str(exc.retry_after_seconds)
        return response

    try:
        context = build_group_insight_context(
            group,
            scope=resolved_scope,
            game_type_code=resolved_game_type_code,
            period=period,
            granularity=granularity if resolved_scope == SCOPE_HALL_OF_FAME else None,
        )
    except GroupInsightContextError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    include_debug = request_include_debug(request.user, payload)

    try:
        result = generate_group_insight(
            context=context,
            preset=preset,
            question=question,
            model_slug=model_slug,
            skip_cache=bool(payload.get("refresh")) or include_debug,
        )
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    except InsightProviderError as exc:
        return JsonResponse({"error": str(exc)}, status=502)

    if not result.cached:
        record_insight_usage(request, user=request.user, model_slug=model_slug)

    persist_insight_model_id(request, model_slug)

    debug = None
    if include_debug:
        resolved_preset = resolve_group_preset(preset, scope=resolved_scope)
        debug = build_contextual_insight_debug(
            mode=f"group:{resolved_scope}",
            system_prompt=GROUP_INSIGHT_SYSTEM_PROMPT,
            context=context,
            preset=resolved_preset,
            question=question,
            user_message=render_group_user_message(
                context=context,
                preset=preset,
                question=question,
            ),
        )

    return _insight_json_response(result=result, context=context, debug=debug)


@demo_or_login_required
@require_POST
def matchup_insight(request: HttpRequest) -> HttpResponse:
    if not insights_feature_enabled():
        return JsonResponse({"error": "Insights are not enabled."}, status=404)

    payload = _parse_json_body(request)
    if payload is None:
        return JsonResponse({"error": "Invalid JSON body."}, status=400)

    game_id = str(payload.get("game_id", "")).strip()
    preset = resolve_matchup_preset(str(payload.get("preset", "")).strip())
    question = str(payload.get("question", "")).strip()
    model_slug = resolve_model_slug(str(payload.get("model", "")).strip())

    if not game_id:
        return JsonResponse({"error": "Missing required fields."}, status=400)
    if preset == PRESET_CUSTOM and not question.strip():
        return JsonResponse({"error": "A custom question is required."}, status=400)

    try:
        game = resolve_matchup_insight_target(
            request,
            user=request.user,
            game_id=game_id,
        )
    except InsightAccessError as exc:
        return JsonResponse({"error": str(exc)}, status=403)

    try:
        check_insight_rate_limit(request, user=request.user, model_slug=model_slug)
    except InsightRateLimitExceeded as exc:
        response = JsonResponse(
            {
                "error": "Rate limit exceeded.",
                "scope": exc.scope,
                "window": exc.window,
                "limit": exc.limit,
            },
            status=429,
        )
        response["Retry-After"] = str(exc.retry_after_seconds)
        return response

    try:
        context = build_matchup_insight_context(game)
    except MatchupInsightContextError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    include_debug = request_include_debug(request.user, payload)

    try:
        result = generate_matchup_insight(
            context=context,
            preset=preset,
            question=question,
            model_slug=model_slug,
            skip_cache=bool(payload.get("refresh")) or include_debug,
        )
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    except InsightProviderError as exc:
        return JsonResponse({"error": str(exc)}, status=502)

    if not result.cached:
        record_insight_usage(request, user=request.user, model_slug=model_slug)

    persist_insight_model_id(request, model_slug)

    debug = None
    if include_debug:
        resolved_preset = resolve_matchup_preset(preset)
        debug = build_contextual_insight_debug(
            mode="matchup",
            system_prompt=MATCHUP_INSIGHT_SYSTEM_PROMPT,
            context=context,
            preset=resolved_preset,
            question=question,
            user_message=render_matchup_user_message(
                context=context,
                preset=preset,
                question=question,
            ),
        )

    return _insight_json_response(result=result, context=context, debug=debug)


def _ask_template_context(request: HttpRequest) -> dict[str, Any]:
    return {
        "insights_enabled": insights_ui_enabled(),
        "insights_ready": insights_feature_enabled(),
        "insight_models": tuple(MODEL_REGISTRY.values()),
        "selected_insight_model": preferred_insight_model_id(request),
    }


def _period_context_for_group(
    group,
    game_type_code: str | None,
    request: HttpRequest,
) -> dict[str, Any]:
    if group is None or not game_type_code:
        return {
            "selected_period": LeaderboardPeriod.all_time(),
            "period_year_options": [],
            "period_month_options": [],
            "period_label": "",
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
        "period_label": selected_period.display_label(),
    }


def _ask_meta(result: AskResult) -> dict[str, Any]:
    meta: dict[str, Any] = {
        "model": result.model_slug,
        "model_label": MODEL_REGISTRY[result.model_slug].label,
        "provider": result.provider,
        "prompt_version": result.prompt_version,
        "context_schema_version": result.context_schema_version,
        "cached": result.cached,
        "input_tokens": result.input_tokens,
        "output_tokens": result.output_tokens,
        "tools_used": list(result.tools_used),
    }
    if result.coverage is not None:
        meta["coverage"] = result.coverage
    return meta


def _ask_example_rows(examples, try_it_urls: dict[str, str]) -> list[dict[str, object]]:
    return [
        {
            "example": example,
            "try_it_url": try_it_urls.get(example.slug),
        }
        for example in examples
    ]


@demo_or_login_required
def ask_page(request: HttpRequest) -> HttpResponse:
    if not insights_ui_enabled():
        raise Http404()

    groups = list(visible_groups(request.user).order_by("name"))
    requested_group = request.GET.get("group") if "group" in request.GET else None
    selected_group = resolve_view_group(
        request,
        requested=requested_group,
        available_groups=groups,
    )

    game_type_codes = (
        game_type_codes_for_group(selected_group) if selected_group else []
    )
    selected_game_type_code = None
    if game_type_codes:
        selected_game_type_code = resolve_game_type_code(
            request,
            requested=request.GET.get("game_type_code", "").strip(),
            available_codes=game_type_codes,
        )

    period_ctx = _period_context_for_group(
        selected_group,
        selected_game_type_code,
        request,
    )
    selected_game_type = (
        get_game_type(selected_game_type_code) if selected_game_type_code else None
    )
    game_type_options = [(code, get_game_type(code).name) for code in game_type_codes]

    filter_summary = ""
    if selected_group:
        filter_summary = leaderboard_filter_summary(
            group_name=selected_group.name,
            game_type_name=selected_game_type.name if selected_game_type else None,
            period_label=period_ctx.get("period_label", ""),
        )

    prefill_question = ""
    raw_question = request.GET.get("question", "").strip()
    if raw_question:
        prefill_question = sanitize_custom_question(raw_question)

    return render(
        request,
        "insights/ask.html",
        {
            "groups": groups,
            "selected_group": selected_group,
            "game_type_options": game_type_options,
            "selected_game_type_code": selected_game_type_code,
            "selected_game_type": selected_game_type,
            "filter_summary": filter_summary,
            "prefill_question": prefill_question,
            "navbar_active_section": "insights",
            **_ask_template_context(request),
            **period_ctx,
        },
    )


@demo_or_login_required
def ask_examples_page(request: HttpRequest) -> HttpResponse:
    if not insights_ui_enabled():
        raise Http404()

    examples_by_reliability = group_ask_examples_by_reliability()
    try_it_urls = try_it_urls_by_slug()
    examples_sections = [
        {
            "label": "Supported",
            "examples": _ask_example_rows(
                examples_by_reliability["supported"],
                try_it_urls,
            ),
        },
        {
            "label": "Partial or unreliable",
            "examples": _ask_example_rows(
                examples_by_reliability["partial"],
                try_it_urls,
            ),
        },
        {
            "label": "Not supported",
            "examples": _ask_example_rows(
                examples_by_reliability["not_supported"],
                try_it_urls,
            ),
        },
    ]

    return render(
        request,
        "insights/ask_examples.html",
        {
            "examples_sections": examples_sections,
            "navbar_active_section": "insights",
            "insights_ready": insights_feature_enabled(),
        },
    )


@demo_or_login_required
def ask_example_detail(request: HttpRequest, slug: str) -> HttpResponse:
    if not insights_ui_enabled():
        raise Http404()

    example = get_ask_example(slug)
    if example is None:
        raise Http404()

    try_it_url = try_it_url_for_example(example)

    return render(
        request,
        "insights/ask_example_detail.html",
        {
            "example": example,
            "try_it_url": try_it_url,
            "navbar_active_section": "insights",
            "insights_ready": insights_feature_enabled(),
        },
    )


@demo_or_login_required
@require_POST
def ask_query(request: HttpRequest) -> HttpResponse:
    if not insights_feature_enabled():
        return JsonResponse({"error": "Insights are not enabled."}, status=404)

    payload = _parse_json_body(request)
    if payload is None:
        return JsonResponse({"error": "Invalid JSON body."}, status=400)

    group_id = str(payload.get("group_id", "")).strip()
    question = str(payload.get("question", "")).strip()
    model_slug = resolve_model_slug(str(payload.get("model", "")).strip())

    if not group_id or not question:
        return JsonResponse({"error": "Missing required fields."}, status=400)

    try:
        group, game_type_code, period = resolve_ask_target(
            request,
            user=request.user,
            group_id=group_id,
            game_type_code=str(payload.get("game_type_code", "")).strip(),
            raw_year=str(payload.get("year", "")),
            raw_month=str(payload.get("month", "")),
        )
    except InsightAccessError as exc:
        return JsonResponse({"error": str(exc)}, status=403)

    try:
        check_insight_rate_limit(request, user=request.user, model_slug=model_slug)
    except InsightRateLimitExceeded as exc:
        response = JsonResponse(
            {
                "error": "Rate limit exceeded.",
                "scope": exc.scope,
                "window": exc.window,
                "limit": exc.limit,
            },
            status=429,
        )
        response["Retry-After"] = str(exc.retry_after_seconds)
        return response

    scope = AskScope(
        group=group,
        period=period,
        default_game_type_code=game_type_code,
        available_game_type_codes=tuple(game_type_codes_for_group(group)),
    )

    include_debug = request_include_debug(request.user, payload)

    try:
        result = generate_ask_response(
            scope=scope,
            question=question,
            model_slug=model_slug,
            period_label=period.display_label(),
            skip_cache=bool(payload.get("refresh")) or include_debug,
            collect_debug=include_debug,
        )
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    except InsightProviderError as exc:
        return JsonResponse({"error": str(exc)}, status=502)

    if not result.cached:
        record_insight_usage(request, user=request.user, model_slug=model_slug)

    persist_insight_model_id(request, model_slug)

    body: dict[str, Any] = {
        "markdown": result.markdown,
        "html": result.html,
        "meta": _ask_meta(result),
    }
    if result.debug is not None:
        body["debug"] = result.debug
    elif include_debug:
        body["debug"] = build_ask_insight_debug(
            question=question,
            user_message=render_ask_user_message(
                question=question,
                group_name=scope.group.name,
                game_type_code=scope.default_game_type_code,
                period_label=period.display_label(),
                player_roster=build_ask_player_roster(scope.group),
                player_hints=build_question_player_hints(scope.group, question),
            ),
            system_prompt=ASK_SYSTEM_PROMPT,
            scope={
                "group_id": scope.group.pk,
                "group_name": scope.group.name,
                "game_type_code": scope.default_game_type_code,
                "period": scope.period.query_params() or {"all_time": True},
                "available_game_types": list(scope.available_game_type_codes),
            },
            player_roster=build_ask_player_roster(scope.group),
            tool_rounds=[],
            tools_used=list(result.tools_used),
            final_answer=result.markdown,
            note="Response served from cache; tool rounds not stored.",
        )

    return JsonResponse(body)
