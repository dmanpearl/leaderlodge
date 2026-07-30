from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from leaderlodge.games.features import (
    apply_feature_selections_to_results_qs,
    feature_catalog_for_game_type,
    feature_summary_labels,
    game_features_response_payload,
    leaderboard_fields_to_selections,
    leaderboard_filter_rows,
    resolve_feature_selections,
    resolve_feature_selections_from_tool_args,
    selections_to_leaderboard_fields,
)
from leaderlodge.games.registry import (
    game_type_shutout_config,
    game_type_supports_shutout,
)
from leaderlodge.games.shutouts import shutout_game_ids

if TYPE_CHECKING:
    from django.db.models import QuerySet


def _resolve_shutout_only(params) -> bool:
    return str(params.get("shutout", "")).strip() in ("1", "true", "on")


@dataclass(frozen=True)
class LeaderboardGameFilters:
    score_type: str | None = None
    double_game: bool | None = None
    half_game: bool | None = None
    shutout_only: bool = False

    def is_active(self) -> bool:
        return bool(self.as_selections()) or self.shutout_only

    def as_selections(self) -> dict[str, str]:
        return leaderboard_fields_to_selections(
            score_type=self.score_type,
            double_game=self.double_game,
            half_game=self.half_game,
        )

    def query_params(self) -> dict[str, str]:
        params = self.as_selections()
        if self.shutout_only:
            params["shutout"] = "1"
        return params

    def without_shutout_scope(self) -> LeaderboardGameFilters:
        """Shutout scoping applies to the games list, not leaderboard standings."""
        if not self.shutout_only:
            return self
        return LeaderboardGameFilters(
            score_type=self.score_type,
            double_game=self.double_game,
            half_game=self.half_game,
            shutout_only=False,
        )


def resolve_leaderboard_game_filters(
    params,
    *,
    game_type_code: str | None,
) -> LeaderboardGameFilters:
    selections = resolve_feature_selections(params, game_type_code=game_type_code)
    fields = selections_to_leaderboard_fields(selections)
    shutout_only = _resolve_shutout_only(params)
    if (
        shutout_only
        and game_type_code
        and not game_type_supports_shutout(game_type_code)
    ):
        shutout_only = False
    return LeaderboardGameFilters(
        score_type=fields["score_type"],
        double_game=fields["double_game"],
        half_game=fields["half_game"],
        shutout_only=shutout_only,
    )


def resolve_leaderboard_game_filters_from_tool_args(
    arguments: dict,
    *,
    game_type_code: str,
) -> LeaderboardGameFilters:
    selections = resolve_feature_selections_from_tool_args(
        arguments,
        game_type_code=game_type_code,
    )
    fields = selections_to_leaderboard_fields(selections)
    shutout_only = bool(arguments.get("shutout_only"))
    if shutout_only and not game_type_supports_shutout(game_type_code):
        shutout_only = False
    return LeaderboardGameFilters(
        score_type=fields["score_type"],
        double_game=fields["double_game"],
        half_game=fields["half_game"],
        shutout_only=shutout_only,
    )


def game_filter_context(
    *,
    game_type_code: str | None,
    selected_filters: LeaderboardGameFilters,
) -> dict:
    if not game_type_code:
        return {
            "game_feature_filters": [],
            "game_filter_labels": [],
        }

    selections = selected_filters.without_shutout_scope().as_selections()
    return {
        "game_feature_filters": leaderboard_filter_rows(
            game_type_code=game_type_code,
            selections=selections,
        ),
        "game_filter_labels": game_filter_summary_labels(
            selected_filters.without_shutout_scope(),
            game_type_code=game_type_code,
        ),
    }


def game_filter_summary_labels(
    filters: LeaderboardGameFilters,
    *,
    game_type_code: str,
) -> list[str]:
    labels = feature_summary_labels(
        filters.as_selections(),
        game_type_code=game_type_code,
    )
    if filters.shutout_only:
        config = game_type_shutout_config(game_type_code)
        if config is not None:
            labels.append(config.label)
    return labels


def apply_shutout_filter_to_games_qs(
    games_qs: QuerySet,
    *,
    game_type_code: str,
    shutout_only: bool,
) -> QuerySet:
    if not shutout_only:
        return games_qs
    if not game_type_supports_shutout(game_type_code):
        return games_qs.none()

    from leaderlodge.games.models import GameParticipantResult

    results = GameParticipantResult.objects.filter(
        game_id__in=games_qs.values("pk")
    ).select_related("game")
    matching_ids = shutout_game_ids(game_type_code, list(results))
    if not matching_ids:
        return games_qs.none()
    return games_qs.filter(pk__in=matching_ids)


def apply_game_filters_to_results_qs(
    results_qs: QuerySet,
    filters: LeaderboardGameFilters,
    *,
    game_type_code: str,
) -> QuerySet:
    filtered = apply_feature_selections_to_results_qs(
        results_qs,
        filters.as_selections(),
        game_type_code=game_type_code,
    )
    if not filters.shutout_only:
        return filtered
    if not game_type_supports_shutout(game_type_code):
        return filtered.none()

    from leaderlodge.games.models import GameParticipantResult

    game_ids = filtered.values_list("game_id", flat=True).distinct()
    all_results = GameParticipantResult.objects.filter(
        game_id__in=game_ids
    ).select_related("game")
    matching_ids = shutout_game_ids(game_type_code, list(all_results))
    if not matching_ids:
        return filtered.none()
    return filtered.filter(game_id__in=matching_ids)
