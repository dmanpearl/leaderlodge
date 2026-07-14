"""Persist Ask the Lodge and contextual insight requests for auditing."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from django.contrib.auth.models import AbstractBaseUser, AnonymousUser
from django.http import HttpRequest, JsonResponse

from leaderlodge.insights.context.group import SCOPE_HALL_OF_FAME, SCOPE_LEADERBOARD
from leaderlodge.insights.models import InsightLog
from leaderlodge.insights.prompts import (
    PRESET_CUSTOM,
    rendered_preset_question_text,
    resolve_group_preset,
    resolve_matchup_preset,
    resolve_preset,
    sanitize_custom_question,
)
from leaderlodge.insights.service import AskResult, InsightResult
from leaderlodge.leaderboards.period import LeaderboardPeriod

if TYPE_CHECKING:
    from leaderlodge.games.models import Game
    from leaderlodge.groups.models import Group, GroupPlayer


def period_to_log_json(period: LeaderboardPeriod | None) -> dict[str, Any]:
    if period is None or not period.is_filtered:
        return {"all_time": True}
    payload: dict[str, Any] = {"all_time": False}
    if period.preset:
        payload["period_preset"] = period.preset
    if period.has_date_range:
        assert period.start_date is not None and period.end_date is not None
        payload["start_date"] = period.start_date.isoformat()
        payload["end_date"] = period.end_date.isoformat()
    if period.year is not None:
        payload["year"] = period.year
    if period.month is not None:
        payload["month"] = period.month
    return payload


def source_for_group_scope(scope: str) -> str:
    if scope == SCOPE_HALL_OF_FAME:
        return InsightLog.Source.GROUP_HALL_OF_FAME
    return InsightLog.Source.GROUP_LEADERBOARD


def resolve_log_user(
    user: AbstractBaseUser | AnonymousUser,
) -> AbstractBaseUser | None:
    if getattr(user, "is_authenticated", False):
        return user  # type: ignore[return-value]
    return None


def resolve_regenerate_of(payload: dict[str, Any]) -> InsightLog | None:
    raw_id = str(payload.get("regenerate_of_id", "")).strip()
    if not raw_id.isdigit():
        return None
    return InsightLog.objects.filter(pk=int(raw_id)).first()


def summarize_insight_context(source: str, context: dict[str, Any]) -> dict[str, Any]:
    if source == InsightLog.Source.PLAYER:
        return {
            "player_label": context.get("player", {}).get("display_label", ""),
            "period_label": context.get("period", {}).get("label", ""),
            "rank": context.get("ranking", {}).get("rank"),
            "games_played": context.get("ranking", {}).get("games_played"),
            "sparse": context.get("data_quality", {}).get("sparse"),
        }
    if source == InsightLog.Source.GROUP_LEADERBOARD:
        return {
            "period_label": context.get("period", {}).get("label", ""),
            "games_in_period": context.get("data_quality", {}).get(
                "total_weighted_games"
            ),
            "sparse": context.get("data_quality", {}).get("sparse"),
        }
    if source == InsightLog.Source.GROUP_HALL_OF_FAME:
        return {
            "granularity": context.get("granularity", ""),
            "period_count": context.get("data_quality", {}).get("period_count"),
            "sparse": context.get("data_quality", {}).get("sparse"),
        }
    if source == InsightLog.Source.MATCHUP:
        return {
            "played_on": context.get("game", {}).get("played_on", ""),
            "player_count": context.get("data_quality", {}).get("player_count"),
            "sparse": context.get("data_quality", {}).get("sparse"),
        }
    return {}


def summarize_ask_scope(
    *,
    group_name: str,
    period_label: str,
) -> dict[str, Any]:
    return {
        "group_name": group_name,
        "period_label": period_label or "All time",
    }


def resolved_preset_key(
    *,
    source: str,
    preset: str,
    group_scope: str = "",
) -> str:
    if source == InsightLog.Source.ASK:
        return ""
    if source == InsightLog.Source.PLAYER:
        return resolve_preset(preset)
    if source in (
        InsightLog.Source.GROUP_LEADERBOARD,
        InsightLog.Source.GROUP_HALL_OF_FAME,
    ):
        return resolve_group_preset(preset, scope=group_scope)
    if source == InsightLog.Source.MATCHUP:
        return resolve_matchup_preset(preset)
    return preset


def question_for_log(
    *,
    source: str,
    preset: str,
    raw_question: str = "",
    group_scope: str = "",
) -> str:
    if source == InsightLog.Source.ASK:
        return sanitize_custom_question(raw_question)
    resolved = resolved_preset_key(
        source=source,
        preset=preset,
        group_scope=group_scope,
    )
    if resolved == PRESET_CUSTOM:
        return sanitize_custom_question(raw_question)
    return rendered_preset_question_text(
        source=source,
        preset=preset,
        group_scope=group_scope,
    )


@dataclass
class InsightLogDraft:
    request: HttpRequest
    payload: dict[str, Any]
    source: str
    preset: str = ""
    raw_question: str = ""
    group_scope: str = ""
    model_slug: str = ""
    group: Group | None = None
    player: GroupPlayer | None = None
    game: Game | None = None
    game_type_code: str = ""
    period: LeaderboardPeriod | None = None
    insight_context: dict[str, Any] | None = None
    context_summary: dict[str, Any] = field(default_factory=dict)

    @property
    def is_regenerate(self) -> bool:
        return bool(self.payload.get("refresh"))

    def save(
        self,
        *,
        http_status: int,
        error_message: str = "",
        answer_markdown: str = "",
        result: InsightResult | AskResult | None = None,
    ) -> InsightLog:
        is_failure = http_status >= 400
        resolved_preset = resolved_preset_key(
            source=self.source,
            preset=self.preset,
            group_scope=self.group_scope,
        )
        question = question_for_log(
            source=self.source,
            preset=self.preset,
            raw_question=self.raw_question,
            group_scope=self.group_scope,
        )
        summary = dict(self.context_summary)
        if self.insight_context and not summary:
            summary = summarize_insight_context(self.source, self.insight_context)

        tools_used: list[str] = []
        coverage = None
        prompt_version = None
        cached = False
        input_tokens = 0
        output_tokens = 0
        if result is not None:
            prompt_version = result.prompt_version
            cached = result.cached
            input_tokens = result.input_tokens
            output_tokens = result.output_tokens
            if isinstance(result, AskResult):
                tools_used = list(result.tools_used)
                coverage = result.coverage

        return InsightLog.objects.create(
            user=resolve_log_user(self.request.user),
            source=self.source,
            preset=resolved_preset,
            question=question,
            is_failure=is_failure,
            http_status=http_status,
            error_message=error_message,
            answer_markdown=answer_markdown,
            is_regenerate=self.is_regenerate,
            regenerate_of=resolve_regenerate_of(self.payload),
            group=self.group,
            player=self.player,
            game=self.game,
            game_type_code=self.game_type_code,
            period=period_to_log_json(self.period),
            model_slug=self.model_slug or (result.model_slug if result else ""),
            prompt_version=prompt_version,
            cached=cached,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            tools_used=tools_used,
            coverage=coverage,
            context_summary=summary,
        )


def json_response_with_log(
    *,
    draft: InsightLogDraft,
    body: dict[str, Any],
    status: int = 200,
    result: InsightResult | AskResult | None = None,
    extra_headers: dict[str, str] | None = None,
) -> JsonResponse:
    is_failure = status >= 400
    error_message = str(body.get("error", "")) if is_failure else ""
    answer_markdown = "" if is_failure else str(body.get("markdown", ""))
    log = draft.save(
        http_status=status,
        error_message=error_message,
        answer_markdown=answer_markdown,
        result=result,
    )
    body = dict(body)
    body["log_id"] = log.pk
    response = JsonResponse(body, status=status)
    if extra_headers:
        for key, value in extra_headers.items():
            response[key] = value
    return response
