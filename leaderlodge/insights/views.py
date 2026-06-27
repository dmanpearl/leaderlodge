"""HTTP views for AI insights."""

from __future__ import annotations

import json

from django.conf import settings
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.http import require_POST

from leaderlodge.core.decorators import demo_or_login_required
from leaderlodge.insights.access import InsightAccessError, resolve_player_insight_target
from leaderlodge.insights.context.player import InsightContextError, build_player_insight_context
from leaderlodge.insights.exceptions import InsightRateLimitExceeded
from leaderlodge.insights.model_selection import persist_insight_model_id
from leaderlodge.insights.providers.base import InsightProviderError
from leaderlodge.insights.prompts import PRESET_CUSTOM, resolve_preset
from leaderlodge.insights.rate_limit import check_insight_rate_limit, record_insight_usage
from leaderlodge.insights.registry import MODEL_REGISTRY, resolve_model_slug
from leaderlodge.insights.service import generate_player_insight


def _configured_api_key(name: str) -> str:
    return (getattr(settings, name, "") or "").strip()


def insights_ui_enabled() -> bool:
    """Show Insights UI when enabled or when API keys are present."""
    if getattr(settings, "INSIGHTS_ENABLED", False):
        return True
    return bool(_configured_api_key("OPENAI_API_KEY") or _configured_api_key("GOOGLE_AI_API_KEY"))


def insights_feature_enabled() -> bool:
    if not getattr(settings, "INSIGHTS_ENABLED", False):
        return False
    return bool(_configured_api_key("OPENAI_API_KEY") or _configured_api_key("GOOGLE_AI_API_KEY"))


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

    try:
        result = generate_player_insight(
            context=context,
            preset=preset,
            question=question,
            model_slug=model_slug,
            skip_cache=bool(payload.get("refresh")),
        )
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    except InsightProviderError as exc:
        return JsonResponse({"error": str(exc)}, status=502)

    if not result.cached:
        record_insight_usage(request, user=request.user, model_slug=model_slug)

    persist_insight_model_id(request, model_slug)

    games_in_period = context.get("data_quality", {}).get("games_in_period", 0)
    return JsonResponse(
        {
            "markdown": result.markdown,
            "html": result.html,
            "meta": {
                "model": result.model_slug,
                "model_label": MODEL_REGISTRY[result.model_slug].label,
                "provider": result.provider,
                "prompt_version": result.prompt_version,
                "context_schema_version": result.context_schema_version,
                "games_in_period": games_in_period,
                "cached": result.cached,
                "input_tokens": result.input_tokens,
                "output_tokens": result.output_tokens,
            },
        }
    )
